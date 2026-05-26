from flask import Flask, request, jsonify
import threading
import requests
import os
import hashlib
import sys
sys.path.append('/workspace/Code')
from server import expand_query, search, generate_answer, extract_relation
from db import get_or_create_user, save_history, save_result, get_user_history
from conversation_manager import ConversationManager

app = Flask(__name__)
manager = ConversationManager()

def get_user_id(data):
    raw_id = data.get("userRequest", {}).get("user", {}).get("id", "unknown")
    return hashlib.sha256(raw_id.encode()).hexdigest()

def get_utterance(data):
    """카카오 요청에서 사용자 발화 추출 (우선순위 순)"""
    detail_params = data.get("action", {}).get("detailParams", {})
    if "user_story" in detail_params:
        return detail_params["user_story"].get("value")
 
    params = data.get("action", {}).get("params", {}).get("user_story")
    if params:
        return params
 
    return data.get("userRequest", {}).get("utterance")
 
 
def expand_query_rag(text: str) -> dict:
    expanded = expand_query(text)
    relation = extract_relation(text)

    return {
        "expanded": expanded,
        "relation": relation 
    }

def analyze_rag(expanded_text: str) -> str:
    docs = search(expanded_text, top_k=3)
    return generate_answer(expanded_text, docs)

@app.route('/situation', methods=['POST'])
def situation():
    """1단계: 사용자 상황 입력 → 쿼리 확장 → 확인 요청"""
    data = request.get_json()
    user_id = get_user_id(data)
    user_input = get_utterance(data)
 
    print(f"\n{'='*50}\n[situation] {user_id}: {user_input}\n{'='*50}\n")
   
    # DB에 유저 등록 (없으면 생성)
    get_or_create_user(user_id)

    # 쿼리 확장
    expanded = expand_query_rag(user_input)

    print(
        f"\n{'='*50}\n"
        f"[situation] {user_id}: {user_input}\n"
	f"관계: {expanded['relation']}\n"
	f"{'='*50}\n"
	)
 
    # manager에 저장
    manager.reset_state(user_id)
    manager.update_state(
        user_id,
        situation=user_input,
        expanded=expanded["expanded"],
        relation=expanded["relation"],
    )
    manager.add_history(user_id, "user", user_input)
 
    response_text = f"입력하신 내용을 이렇게 이해했어요:\n\n'{expanded['expanded']}'\n\n맞나요?"
    
    manager.add_history(user_id, "assistant", response_text)
 
    return jsonify({
        "version": "2.0",
        "template": {
            "outputs": [
                {"simpleText": {"text": response_text}}
            ],
            "quickReplies": [
                {
                    "label": "네",
                    "action": "block",
                    "blockId": "69df7b7d9e38951753f9bd73"   # 상황 분석 블록
                },
                {
                    "label": "다시 입력",
                    "action": "block",
                    "blockId": "69fac84ffd39d41e08466e45"   # 추가 입력 블록
                },
                {
                    "label": "초기화",
                    "action": "block",
                    "blockId": "69cccfd0d3cf917d7a339478"  # 사용자상황입력 블록으로
		}
            ]
        }
    })

@app.route('/situation_add', methods=['POST'])
def situation_add():
    """2단계(선택): 사용자가 '다시 입력' 선택 → 추가 내용 받아서 이전 내용과 합치기"""
    data = request.get_json()
    user_id = get_user_id(data)
    add_input = get_utterance(data)
 
    # 이전 상태 불러오기
    state = manager.get_state(user_id)
    prev_situation = state.get("situation", "")
 
    # 이전 내용 + 추가 내용 합치기
    merged = f"{prev_situation} {add_input}".strip()
 
    # 다시 쿼리 확장
    expanded = expand_query_rag(merged)

    print(
        f"\n{'='*50}\n"
        f"[situation_add] {user_id}: {merged}\n"
        f"관계: {expanded['relation']}\n"
        f"{'='*50}\n"
    )
 
    # manager 업데이트
    manager.update_state(
        user_id,
        situation=merged,
        expanded=expanded["expanded"],
        relation=expanded["relation"],
    )
    manager.add_history(user_id, "user", add_input)

    response_text = f"입력하신 내용을 이렇게 이해했어요:\n\n'{expanded['expanded']}'\n\n맞나요?"
    
    manager.add_history(user_id, "assistant", response_text)
 
    return jsonify({
        "version": "2.0",
        "template": {
            "outputs": [
                {"simpleText": {"text": response_text}}
            ],
            "quickReplies": [
                {
                    "label": "네",
                    "action": "block",
                    "blockId": "69df7b7d9e38951753f9bd73"   # 상황 분석 블록
                },
                {
                    "label": "다시 입력",
                    "action": "block",
                    "blockId": "69fac84ffd39d41e08466e45"   # 추가 입력 블록
                },
	        {
     		    "label": "초기화",
    		    "action": "block",
       		    "blockId": "69cccfd0d3cf917d7a339478"  # 사용자상황입력 블록으로
    		}
            ]
        }
    })

def send_callback(callback_url, result_text):

    response_data = {
        "version": "2.0",
        "template": {
            "outputs": [
                {
                    "simpleText": {
                        "text": result_text
                    }
                }
            ],
            "quickReplies": [
                {
                    "label": "확인했어요",
                    "action": "block",
                    "blockId": "69df2cf79e38951753f9a469"
                }
            ]
        }
    }

    requests.post(callback_url, json=response_data)

@app.route('/analysis', methods=['POST'])
def analysis():

    data = request.get_json()

    user_id = get_user_id(data)

    callback_url = data["userRequest"]["callbackUrl"]

    print(f"\n{'='*50}\n[analysis] {user_id}\n{'='*50}\n")

    state = manager.get_state(user_id)

    expanded_text = state.get("expanded", "")

    if not expanded_text:
        return jsonify({
            "version": "2.0",
            "template": {
                "outputs": [
                    {
                        "simpleText": {
                            "text": "이전 입력 내용을 찾을 수 없어요. 처음부터 다시 시작해주세요."
                        }
                    }
                ]
            }
        })

    thread = threading.Thread(
        target=process_analysis,
        args=(callback_url, user_id, expanded_text)
    )

    thread.start()

    return jsonify({
        "version": "2.0",
        "useCallback": True
    })

@app.route('/user_save', methods=['POST'])
def user_save():
    """4단계(선택): 사용자 동의 후 DB에 결과 저장 → 세션 삭제"""
    data = request.get_json()
    user_id = get_user_id(data)
 
    print(f"\n{'='*50}\n[user_save] {user_id}\n{'='*50}\n")
 
    state = manager.get_state(user_id)
    relation  = state.get("relation", "")
    situation = state.get("situation", "")
    result    = state.get("result", "")
 
    if not result:
        return jsonify({
            "version": "2.0",
            "template": {
                "outputs": [
                    {"simpleText": {"text": "저장할 내용이 없어요. 처음부터 다시 시작해주세요."}}
                ]
            }
        })

    # DB 저장
    history_id = save_history(user_id, relation, situation)
    save_result(history_id, result)
 
    # 세션 삭제
    manager.reset_state(user_id)
 
    return jsonify({
        "version": "2.0",
        "template": {
            "outputs": [
                {
                    "simpleText": {
                        "text": "✅ 저장이 완료됐어요.\n필요할 때 언제든지 다시 확인할 수 있어요\n\n대화 내용은 3개월마다 삭제됩니다."
                    }
                }
            ]
        }
    })

@app.route('/end', methods=['POST'])
def end():
    """저장 안 함 선택 → 세션만 삭제"""
    data = request.get_json()
    user_id = get_user_id(data)
 
    manager.reset_state(user_id)
 
    return jsonify({
        "version": "2.0",
        "template": {
            "outputs": [
                {
                    "simpleText": {
                        "text": "대화를 종료할게요.\n도움이 필요하면 언제든지 다시 찾아와요. 💙"
                    }
                }
            ]
        }
    })

def process_analysis(callback_url, user_id, expanded_text):

    try:
        result_text = analyze_rag(expanded_text)

        manager.update_state(user_id, result=result_text)

        manager.add_history(user_id, "assistant", result_text)

        send_callback(callback_url, result_text)

    except Exception as e:

        print("분석 오류:", e)

        send_callback(
            callback_url,
            "분석 중 오류가 발생했습니다."
        )

@app.route('/history', methods=['POST'])
def history():

    data = request.get_json()

    user_id = get_user_id(data)

    histories = get_user_history(user_id)

    if not histories:

        text = "저장된 상담 기록이 없어요."

    else:

        text = "최근 상담한 5개의 기록을 보여드릴게요.\n\n"

        history_texts = []

        for i, (history_id, result_text, created_at) in enumerate(histories):

            history_texts.append(
                f"📌 상담 기록 {i+1}\n"
                f"🕒 {created_at.strftime('%Y-%m-%d %H:%M')}\n\n"
                f"{result_text}"
            )

        text += "\n\n────────────\n\n".join(history_texts)

    return jsonify({
        "version": "2.0",
        "template": {
            "outputs": [
                {
                    "simpleText": {
                        "text": text
                    }
                }
                       ]
                   }
    })
           
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
