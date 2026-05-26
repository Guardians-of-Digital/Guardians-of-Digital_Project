import pdfplumber
import re
import json
import os
from langchain_text_splitters import RecursiveCharacterTextSplitter

def is_valid_chunk(content):
    # 1. 깨진 문자 포함 제거
    if '(cid:' in content:
        return False

    # 2. 너무 짧은 청크 제거
    if len(content.strip()) < 100:
        return False

    # 3. 한글 비율 너무 낮은 청크 제거
    korean_ratio = len(re.findall(r'[\uAC00-\uD7A3]', content)) / max(len(content), 1)
    if korean_ratio < 0.2:
        return False

    # 4. 표 파편 제거 (| 기호 과다)
    if content.count('|') > 5:
        return False

    # 5. 서식/양식 키워드 제거
    form_keywords = [
        '210mm×297mm', '서명 또는 인', '백상지',
        '< 답 >', '※ 문서 발송 번호', '색상이 어두운 난',
        '접수 일자 | 접수 방법'
    ]
    if any(kw in content for kw in form_keywords):
        return False

    # 6. 표 파편 패턴 제거 (유형|성격|적용법률)
    if re.search(r'유형.{0,5}성격.{0,5}적용법률', content):
        return False

    # 7. PART 헤더 반복 많은 청크 제거
    part_count = len(re.findall(r'PART\s*\d+', content))
    if part_count > 2:
        return False

    # 8. ~ 특수문자로만 이루어진 항목 나열 청크 제거
    tilde_lines = sum(1 for l in content.split('\n') if '~' in l and len(l.strip()) < 30)
    if tilde_lines > 2:
        return False

    # 9. URL/연락처 위주 청크 제거
    url_count = len(re.findall(r'https?://', content))
    if url_count > 2:
        return False

    # 10. 목차성 청크 제거 (짧은 줄 비율 높은 것)
    lines = content.strip().split('\n')
    short_lines = sum(1 for l in lines if len(l.strip()) < 20)
    if short_lines / max(len(lines), 1) > 0.6:
        return False

    # 11. 법조문만 나열된 청크 제거
    law_only = re.findall(r'제\d+조|제\d+항|제\d+호', content)
    if len(law_only) > 8 and len(content) < 400:
        return False
    
    # 페이지 번호 + 빈 표 파편 패턴 제거 (예: "38 |  |", "39 |  |")
    if re.search(r'\d+\s*\|\s*\|', content):
        return False

    # 앞 청크와 내용이 거의 동일한 중복 청크 제거
    # | 로 시작하는 표 파편이 본문과 중복되는 경우
    lines = content.strip().split('\n')
    if lines[-1].strip().endswith('|  |'):
        return False
    
    # 기존 is_valid_chunk에 추가

    # | 로 시작하는 표 파편 제거
    # 기존 코드 교체
# content.strip().startswith('|') → 아래로 변경

# | 기호가 3개 이상이면 표 파편으로 간주
    if content.count('|') >= 3:
        return False

    # 단계 + 확인사항 패턴 (표 중복)
    if re.search(r'단계\s*\|\s*확인사항', content):
        return False

    # URL만 있는 청크
    url_count = len(re.findall(r'https?://', content))
    if url_count >= 2 and len(content) < 400:
        return False

    # 숫자+빈 표 파편 패턴 제거 (예: "1 2 3 4 | 1 2 3 4")
    if re.search(r'(\d\s*){2,}\|\s*(\d\s*){2,}', content):
        return False
    
    # 전체 내용에서 | 비율이 높은 청크 제거
    pipe_ratio = content.count('|') / max(len(content), 1)
    if pipe_ratio > 0.02:
        return False

    # | 로 시작하는 표 파편 제거 (이미 있으면 강화)
    if content.strip().startswith('|'):
        return False

    # 표 구조가 뒤섞인 청크 제거
    # "설치형/직접 촬영형" 같은 표 헤더가 본문에 섞인 패턴
    table_noise_keywords = [
        '설치형/직접 촬영형',
        '촬영물 동의 없이 정보통신망을 이',
        '유포 및 용하여 유포/재유포',
    ]
    if any(kw in content for kw in table_noise_keywords):
        return False
    return True

def parse_pdf_hybrid(pdf_path):
    full_text = ""
    
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            
            # 표 추출
            table_text = ""
            try:
                tables = page.extract_tables(table_settings={
                    "vertical_strategy": "lines",
                    "horizontal_strategy": "lines",
                    "snap_tolerance": 3,
                    "join_tolerance": 3,
                    "edge_min_length": 3,
                    "min_words_vertical": 1,
                    "min_words_horizontal": 1,
                })
                if tables:
                    for table in tables:
                        for row in table:
                            row_cleaned = []
                            for cell in row:
                                if cell:
                                    cell_text = cell.replace('\n', ' ').strip()
                                    row_cleaned.append(cell_text)
                                else:
                                    row_cleaned.append("")
                            if any(row_cleaned):
                                table_text += " | ".join(row_cleaned) + "\n"
            except Exception as e:
                print(f"  표 추출 오류: {e}")
            
            # 일반 텍스트 추출
            text = page.extract_text() or ""
            
            lines = text.split('\n')
            cleaned = []
            for line in lines:
                line = line.strip()
                if not line or len(line) < 5:
                    continue
                if '판결서 인터넷열람 사이트' in line:
                    continue
                if '비실명처리일자' in line:
                    continue
                line = re.sub(r'^-\s*\d+\s*-$', '', line).strip()
                if not line:
                    continue
                normal = len(re.findall(r'[\uAC00-\uD7A3a-zA-Z0-9\s\.\,\!\?\(\)\:\;\-\']', line))
                if normal / max(len(line), 1) > 0.5:
                    cleaned.append(line)
            
            full_text += '\n'.join(cleaned) + '\n'
            if table_text:
                full_text += table_text + '\n'
    
    return full_text

def chunk_text(text, filename, category):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=["\n\n", "\n", ".", " "]
    )
    chunks = splitter.split_text(text)
    
    result = []
    for i, chunk in enumerate(chunks):
        chunk = chunk.strip()
        
        # 후처리 필터링
        if not is_valid_chunk(chunk):
            continue
        
        result.append({
            "content": chunk,
            "source": filename,
            "category": category,
            "chunk_id": i,
            "total_chunks": len(chunks)
        })
    return result

# =====================
# 여기서 경로/카테고리 설정
pdf_folder = '/Users/jeongmin/Desktop/Capstone/Data/Guideline'
output_path = '/Users/jeongmin/Desktop/Capstone/Data/guideline_chunks9.json'
category = "가이드라인"
# =====================

all_chunks = []

pdf_files = [f for f in os.listdir(pdf_folder) if f.endswith('.pdf')]
print(f"총 {len(pdf_files)}개 PDF 발견")

for i, filename in enumerate(pdf_files):
    pdf_path = os.path.join(pdf_folder, filename)
    print(f"[{i+1}/{len(pdf_files)}] 처리 중: {filename}")
    
    try:
        text = parse_pdf_hybrid(pdf_path)
        if len(text) < 100:
            print(f"  ⚠️ 텍스트 너무 짧음 - 스킵")
            continue
        chunks = chunk_text(text, filename, category)
        all_chunks.extend(chunks)
        print(f"  ✅ {len(chunks)}개 청크 생성")
    except Exception as e:
        print(f"  ❌ 오류: {e}")

with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(all_chunks, f, ensure_ascii=False, indent=2)

print(f"\n✅ 완료! 총 {len(all_chunks)}개 청크 저장됨")
print(f"저장 위치: {output_path}")