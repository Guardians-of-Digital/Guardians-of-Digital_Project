import json
import os
import glob
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from langchain_text_splitters import RecursiveCharacterTextSplitter

# 1. 임베딩 모델 로드 (multilingual-e5-large로 변경)
print("모델 로딩 중...")
model = SentenceTransformer("intfloat/multilingual-e5-large")
print("모델 로딩 완료!")

# 2. 청킹 설정 (300/30으로 변경)
splitter = RecursiveCharacterTextSplitter(
    chunk_size=300,
    chunk_overlap=30,
    separators=["\n\n", "\n", ".", " "]
)

all_chunks = []

# 3. 판결문 로드 및 재청킹
print("\n판결문 로드 중...")
judgement_files = glob.glob("/workspace/judicial_precedent2/*.json")
for filepath in judgement_files:
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            chunks = json.load(f)
        for chunk in chunks:
            sub_chunks = splitter.split_text(chunk['content'])
            for i, sub in enumerate(sub_chunks):
                if len(sub.strip()) < 50:
                    continue
                all_chunks.append({
                    "content": sub.strip(),
                    "source": chunk['source'],
                    "category": chunk['category'],
                    "chunk_id": len(all_chunks)
                })
    except Exception as e:
        print(f"스킵: {filepath} - {e}")
print(f"판결문 청크: {len(all_chunks)}개")

# 4. 가이드라인 로드 및 재청킹
print("가이드라인 로드 중...")
guideline_count_before = len(all_chunks)
guideline_path = "/workspace/guideline_chunks9.json"
if os.path.exists(guideline_path):
    with open(guideline_path, 'r', encoding='utf-8') as f:
        guideline_chunks = json.load(f)
    for chunk in guideline_chunks:
        sub_chunks = splitter.split_text(chunk['content'])
        for sub in sub_chunks:
            if len(sub.strip()) < 50:
                continue
            all_chunks.append({
                "content": sub.strip(),
                "source": chunk['source'],
                "category": chunk['category'],
                "chunk_id": len(all_chunks)
            })
    print(f"가이드라인 청크: {len(all_chunks) - guideline_count_before}개")

# 5. 질답 데이터 로드
print("질답 데이터 로드 중...")
qa_count_before = len(all_chunks)
qa_path = "/workspace/260404_질의데이터셋_추가_최연우.json"
if os.path.exists(qa_path):
    with open(qa_path, 'r', encoding='utf-8') as f:
        qa_data = json.load(f)
    for item in qa_data:
        question = item.get('question', item.get('input', ''))
        answer = item.get('answer', item.get('output', ''))
        all_chunks.append({
            "content": f"질문: {question}\n답변: {answer}",
            "source": qa_path,
            "category": "질답",
            "chunk_id": len(all_chunks)
        })
    print(f"질답 청크: {len(all_chunks) - qa_count_before}개")

print(f"\n총 청크 수: {len(all_chunks)}개")

# 6. 임베딩 생성
texts = [chunk['content'] for chunk in all_chunks]
print("\n임베딩 시작...")
embeddings = model.encode(texts, batch_size=32, show_progress_bar=True)
print(f"임베딩 완료! 벡터 크기: {embeddings.shape}")

# 7. Qdrant 저장
print("\nQdrant 저장 중...")
client = QdrantClient(path="/workspace/qdrant_db")

collection_name = "capstone_rag"
if client.collection_exists(collection_name):
    client.delete_collection(collection_name)

client.create_collection(
    collection_name=collection_name,
    vectors_config=VectorParams(
        size=embeddings.shape[1],
        distance=Distance.COSINE
    )
)

points = []
for i, (chunk, embedding) in enumerate(zip(all_chunks, embeddings)):
    points.append(PointStruct(
        id=i,
        vector=embedding.tolist(),
        payload={
            "content": chunk['content'],
            "source": chunk['source'],
            "category": chunk['category'],
            "chunk_id": chunk.get('chunk_id', i)
        }
    ))

batch_size = 100
for i in range(0, len(points), batch_size):
    client.upsert(collection_name=collection_name, points=points[i:i+batch_size])
    print(f"저장 중... {min(i+batch_size, len(points))}/{len(points)}")

print(f"\n완료! 총 {len(points)}개 저장됨")

# 8. 검색 테스트
print("\n--- 검색 테스트 ---")
queries = [
    "직장 내 괴롭힘 피해자가 해야 할 일",
    "상사가 욕설을 하면 어떻게 해야 하나요",
    "직장 내 괴롭힘 신고 방법"
]

for query in queries:
    print(f"\n쿼리: {query}")
    query_vector = model.encode(query).tolist()
    results = client.query_points(
        collection_name=collection_name,
        query=query_vector,
        limit=3
    ).points
    for i, result in enumerate(results):
        print(f"[{i+1}] 유사도: {result.score:.4f} | 카테고리: {result.payload['category']}")
        print(f"    내용: {result.payload['content'][:150]}")