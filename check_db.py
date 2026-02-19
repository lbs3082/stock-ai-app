import sqlite3

# 1. DB 파일 열기
try:
    conn = sqlite3.connect("stocks.db")
    cursor = conn.cursor()

    # 2. 데이터 개수 세기
    cursor.execute("SELECT count(*) FROM stock_info")
    count = cursor.fetchone()[0]

    # 3. 데이터 5개만 뽑아서 보여주기
    cursor.execute("SELECT * FROM stock_info LIMIT 5")
    rows = cursor.fetchall()

    print(f"\n📊 검사 결과: 총 {count}개의 주식 종목이 들어있습니다!")
    print("-" * 30)
    print("미리보기 (상위 5개):")
    for row in rows:
        print(f"코드: {row[0]}, 이름: {row[1]}, 시장: {row[2]}")
    print("-" * 30)

    conn.close()

except Exception as e:
    print(f"❌ 오류 발생: {e}")
    print("파일이 없거나 손상되었습니다. init_db.py를 다시 실행하세요.")