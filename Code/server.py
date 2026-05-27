import torch
import os
import re
from transformers import AutoTokenizer, AutoModelForCausalLM
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from conversation_manager import ConversationManager

os.environ["HF_HOME"] = "/workspace/huggingface_cache"

# 모델 로드
print("모델 로딩 중...")
tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-7B-Instruct")
model = AutoModelForCausalLM.from_pretrained(
    "Qwen/Qwen2.5-7B-Instruct",
    torch_dtype=torch.float16,
    device_map="auto"
)
model.eval()

embedding_model = SentenceTransformer("intfloat/multilingual-e5-large")
qdrant_client = QdrantClient(path="/workspace/qdrant_db")
manager = ConversationManager()
print("모델 로딩 완료!")

# Query Expansion
def expand_query(user_input):
    prompt = f"""당신은 직장 내 괴롭힘 관련 문서 검색 시스템입니다.
사용자 입력을 벡터 검색에 최적화된 명사형 질문으로 변환하세요.
추가 설명 없이 변환된 질문만 출력하세요.

입력: 이거 괴롭힘 맞아요?
변환: 직장 내 괴롭힘 해당 여부 판단 기준

입력: 야 너 이따위로 일할 거면 꺼져
변환: 상사의 모욕적 발언이 직장 내 괴롭힘에 해당하는지 여부

입력: 어떻게 해야 하죠
변환: 직장 내 괴롭힘 피해자 대응 방법 및 조치

입력: 신고하면 불이익 받나요
변환: 직장 내 괴롭힘 신고 후 불이익 처우 금지 규정

입력: 증거가 없는데 신고할 수 있나요
변환: 직장 내 괴롭힘 증거 없이 신고 가능 여부

입력: 상사가 매일 욕해요
변환: 상사의 반복적 욕설이 직장 내 괴롭힘에 해당하는지 여부

입력: 회식 강요하는데 어떻게 해요
변환: 회식 강요 행위의 직장 내 괴롭힘 해당 여부 및 대응 방법

입력: 저만 따돌리는 것 같아요
변환: 직장 내 따돌림 및 배제 행위 괴롭힘 해당 여부

입력: 퇴사 종용하는데 이게 맞아요
변환: 직장 내 퇴사 강요 행위 괴롭힘 해당 여부

입력: 회사에서 아무것도 안 해줘요
변환: 직장 내 괴롭힘 신고 후 회사 미조치 시 대응 방법

입력: {user_input}
변환:"""

    messages = [{"role": "user", "content": prompt}]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer([text], return_tensors="pt").to("cuda")

    with torch.no_grad():
        outputs = model.generate(**inputs, max_new_tokens=50, temperature=0.1)

    response = tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
    return response.strip().split("\n")[0]

def extract_relation(user_input):
    prompt = f"""다음 상황에서 상대와의 직급 관계를 분류하세요.

선택지:
- 상하
- 동일직급
- 불명확

판단 기준:
- 팀장, 부장, 사장, 관리자, 선배 등이 사용자보다 높은 위치면 → 상하
- 후배, 부하직원 등이 등장해도 → 상하
- 동료, 같은 팀원, 같은 직급이면 → 동일직급
- 관계를 알 수 없으면 → 불명확

추가 설명 없이 선택한 단어만 출력하세요.

예시1:
입력: 팀장이 저한테만 욕하고 무시해요
출력: 상하

예시2:
입력: 같은 팀 사람이 계속 따돌려요
출력: 동일직급

예시3:
입력: 후배 직원이 저를 비웃어요
출력: 상하

예시4:
입력: 회사에서 괴롭힘당하는 것 같아요
출력: 불명확

입력: {user_input}
출력:"""

    messages = [
        {"role": "user", "content": prompt}
    ]

    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation=True
    )
    inputs = tokenizer(
        [text],
        return_tensors="pt"
    ).to("cuda")

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=10,
            temperature=0.1
        )

    response = tokenizer.decode(
        outputs[0][inputs.input_ids.shape[1]:],
        skip_special_tokens=True
    ).strip()

    valid_relations = ["상하", "동일직급", "불명확"]

    for relation in valid_relations:
        if relation in response:
            return relation

    return "불명확"

# RAG 검색
def search(query, top_k=3):
    query_vector = embedding_model.encode(query).tolist()
    results = qdrant_client.query_points(
        collection_name="capstone_rag",
        query=query_vector,
        limit=top_k
    ).points
    return results

# 답변 생성
def generate_answer(user_input, docs):
    context = ""
    for i, doc in enumerate(docs):
        context += f"[참고 문서 {i+1}] ({doc.payload['category']})\n"
        context += f"{doc.payload['content']}\n\n"

    messages = [
        {
            "role": "system",
            "content": f"""You must respond in Korean only. Never use Chinese, English, or any other language.
당신은 직장 내 괴롭힘 전문 한국어 상담사입니다.
반드시 한국어로만 답변하세요.
답변 형식:
1차 판단
판단 기준
지금 바로 할 일
회사 의무
신고 방법
회사 미조치 시 대응
추가 안내

참고 문서:
{context}"""
        },
        {
            "role": "user",
            "content": f"user: {user_input}"
        }
    ]

    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer([text], return_tensors="pt").to("cuda")
    import time

    start = time.time()
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=2048,
	    temperature=0.3,
            do_sample=True,
            repetition_penalty=1.1,
            eos_token_id=tokenizer.eos_token_id
        )
    print("생성 시간:", time.time() - start)

    response = tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
    return response.strip()

