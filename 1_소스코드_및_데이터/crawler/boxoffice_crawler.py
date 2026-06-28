import os
import requests
import pandas as pd
from time import sleep

from _env import load_env

# KOBIS(영화진흥위원회) OpenAPI 키 — https://www.kobis.or.kr/kobisopenapi 에서 발급
# 키는 코드에 직접 적지 않고 crawler/.env 의 KOBIS_API_KEY 에서 읽는다.
load_env()
MY_KEY = os.environ.get("KOBIS_API_KEY", "")
if not MY_KEY:
    raise SystemExit("KOBIS_API_KEY 가 없습니다. crawler/.env 에 KOBIS_API_KEY=... 를 추가하세요.")

# 1. 수집하고 싶은 연도 설정
target_year = "2025"

start_date = f"{target_year}0101"
end_date = f"{target_year}1231"

# 2. 날짜 리스트 생성 및 데이터 수집
date_list = pd.date_range(start=start_date, end=end_date).strftime("%Y%m%d")
all_data = []

print(f"{target_year}년도 데이터를 가져오기 시작합니다 (총 {len(date_list)}일)...")

for target_date in date_list:
    url = f"http://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json?key={MY_KEY}&targetDt={target_date}"
    
    try:
        response = requests.get(url)
        data = response.json()
        
        if 'boxOfficeResult' in data:
            daily_list = data['boxOfficeResult'].get('dailyBoxOfficeList', [])
            for movie in daily_list:
                movie['targetDt'] = target_date 
                all_data.append(movie)
            
            # 진행 상황을 알기 쉽게 출력
            if int(target_date) % 10 == 0: # 10일 단위로 출력
                print(f"{target_date} 수집 중... (현재 {len(all_data)}건)")
            
    except Exception as e:
        print(f"{target_date} 오류: {e}")
    
    sleep(0.1)

# 3. 파일 이름 자동 생성 및 저장
if all_data:
    df = pd.DataFrame(all_data)
    file_name = f"boxoffice_{target_year}.csv" # 예: boxoffice_2013.csv
    df.to_csv(file_name, index=False, encoding="utf-8-sig")
    print(f"\n--- 성공! {target_year}년도 데이터를 '{file_name}'로 저장했습니다. ---")
