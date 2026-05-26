import fitz
import re
import os

def parse_judgment(pdf_path):
    doc = fitz.open(pdf_path)
    full_text = ""
    
    for page in doc:
        text = page.get_text()
        full_text += text
    
    # 불필요한 내용 제거
    lines = full_text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        line = line.strip()
        if len(line) < 5:
            continue
        if re.match(r'^[-\s]*\d+[-\s]*$', line):
            continue
        cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines)

# 테스트
pdf_path = '/Users/jeongmin/Desktop/Capstone/Data/judicial_precedent/헌재 2003헌마282.pdf'
result = parse_judgment(pdf_path)
print(result[:1000])