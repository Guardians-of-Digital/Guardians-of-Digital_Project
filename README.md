# Guardians of Digital

직장 내 괴롭힘 및 사이버불링 상황을 분석하고 대응 가이드를 제공하는 AI 기반 상담 보조 챗봇 시스템입니다. 

카카오톡 챗봇 환경에서 사용자의 상황 설명을 입력받아 RAG(Retrieval-Augmented Generation) 기반 분석을 수행하고, 괴롭힘 여부 및 대응 방안을 제공합니다.

---
- 프로젝트명 : RAG 기반 직장 내 괴롭힘 상담 챗봇 시스템
- 개발 기간 : 2026.03 ~ 2026.06
- 개발 목적 :
  - 직장 내 괴롭힘 및 사이버불링 상황에 대한 초기 대응 지원
  - AI 기반 실시간 분석 및 대응 가이드 제공
  - 카카오톡 기반 접근성 높은 상담 보조 시스템 구현

---

## 주요 기능

### 직장 내 괴롭힘 분석
- 사용자의 상황 설명 기반 괴롭힘 여부 분석
- 문맥 기반 위험도 판단

### Query Expansion 기반 검색 개선
- 짧고 모호한 사용자 입력을 검색 최적화 질의문으로 확장
- RAG 기반 유사도 검색 정확도 향상

### RAG 기반 응답 생성
- 판례 및 가이드라인 기반 대응 가이드 제공
- Qdrant 벡터 DB 기반 유사 문서 검색

### 카카오톡 챗봇 연동
- 카카오 오픈빌더 기반 챗봇 구현
- Flask 서버와 REST API 연동

### 사용자 데이터 관리
- 사용자 입력 및 분석 결과 저장
- SHA-256 기반 사용자 ID 비식별화

---

## 기술 스택

### Backend
- Python
- Flask
- MySQL

### AI / NLP
- Qwen2.5-7B-Instruct
- RAG
- LangChain
- Jina Embeddings v3

### Vector Database
- Qdrant

### Chatbot
- Kakao OpenBuilder
---

## 시스템 구조

```text
사용자
  ↓
카카오톡 챗봇
  ↓
Flask 서버
  ↓
Query Expansion
  ↓
Qdrant 벡터 검색
  ↓
LLM 응답 생성
  ↓
카카오톡 응답 반환
