import os
from dotenv import load_dotenv
from openai import OpenAI

# 1. .env 파일의 환경변수를 불러옵니다.
load_dotenv()

# 2. 클라이언트를 초기화합니다. (자동으로 OPENAI_API_KEY를 찾습니다)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

try:
    # 3. 간단한 Hello World 요청을 보냅니다.
    response = client.chat.completions.create(
        model="gpt-3.5-turbo", # 또는 "gpt-4"
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "API 연결 테스트입니다. '성공'이라고 대답해줘."}
        ]
    )

    # 4. 결과 출력
    print("--- API 응답 결과 ---")
    print(response.choices[0].message.content)
    print("\n연결에 성공했습니다!")

except Exception as e:
    print(f"오류가 발생했습니다: {e}")