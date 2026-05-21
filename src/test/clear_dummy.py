"""
Firebase lost_items 컬렉션의 모든 문서를 삭제합니다.
실행 방법 (프로젝트 루트에서):
  python src/test/clear_dummy.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import firebase_admin
from firebase_admin import credentials, firestore

KEY_PATH = os.path.join(os.path.dirname(__file__), "..", "backend", "firebase-key.json")

if not firebase_admin._apps:
    cred = credentials.Certificate(KEY_PATH)
    firebase_admin.initialize_app(cred)

db = firestore.client()

def main():
    docs = list(db.collection("lost_items").stream())
    if not docs:
        print("삭제할 데이터가 없습니다.")
        return

    print(f"총 {len(docs)}개 문서를 삭제합니다...")
    for doc in docs:
        doc.reference.delete()
        print(f"  🗑️  삭제: {doc.id}")

    print("\n완료! lost_items 컬렉션이 비워졌습니다.")

if __name__ == "__main__":
    main()
