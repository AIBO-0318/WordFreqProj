from selenium import webdriver
import pickle
import time

driver = webdriver.Chrome()
driver.get("https://pedia.watcha.com/ko-KR")

# 직접 로그인할 시간 30초 줌
print("30초 안에 브라우저에서 직접 로그인해줘!")
time.sleep(30)

# 로그인 후 쿠키 저장
pickle.dump(driver.get_cookies(), open("watcha_cookie.pkl", "wb"))
print("쿠키 저장 완료!")
driver.quit()
