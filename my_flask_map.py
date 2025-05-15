# --- 0. 필요한 도구들 가져오기 ---
from flask import Flask, render_template_string
import folium
import json
import requests
import os
import urllib.parse
import pandas as pd
import time
import urllib3
# SSL 경고 메시지를 비활성화합니다. verify=False 사용 시 함께 사용하는 것이 일반적입니다.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 1. 기본 설정 ---
app = Flask(__name__)

# JSON 파일 경로 설정 (절대 경로 또는 스크립트 기준으로 상대 경로 설정 권장)
# 예: 현재 스크립트 파일과 같은 디렉토리에 저장하고 싶다면 './aptData_detailed_20240507.js'
JSON_FILE_PATH = r'C:\Users\Halla\Documents\청약홈 지도 잘되는거\aptData_detailed_20240507 (1).js'

# 청약홈 API 서비스 키 (디코딩된 값 사용 권장 또는 urllib.parse.unquote 사용)
# 제공해주신 키는 URL 인코딩된 상태입니다. 아래 코드는 인코딩된 상태로 사용합니다.
USER_SERVICE_KEY = "Xq4RTyI675QQJTsqDCbAAOvGJ2KxPSu89MfhUVWseHhKLrk%2FmDqkZeIDFV%2Fk7PjB6DKwjgJzNi9rBpWHUJRSWg%3D%3D"
CHEONGYAK_API_BASE_URL = "https://api.odcloud.kr/api/ApplyhomeInfoDetailSvc/v1/getAPTLttotPblancDetail"
API_PER_PAGE = 10000 # API가 한번에 가져올 수 있는 최대 데이터 수
NEW_API_DATA_FILE = 'latest_cheongyak_data_from_api.json' # API 원본 저장 파일명

# Kakao REST API 키
KAKAO_KEY = "992f9b51e8277a1fee0485197ee414b5"

# --- 2. 청약홈에서 새 정보 가져오는 부분 (사용하지 않는 함수지만 남겨둡니다) ---
# 이 함수는 raw 데이터를 가져오는 예시이며, refresh_data 함수에서 데이터를 가공하여 사용합니다.
def get_latest_data_from_cheongyak_home():
    print(f"청약홈 API({CHEONGYAK_API_BASE_URL})에서 최신 정보를 가져오려고 시도합니다...")
    full_api_url = f"{CHEONGYAK_API_BASE_URL}?page=1&perPage={API_PER_PAGE}&serviceKey={USER_SERVICE_KEY}"

    try:
        # 청약홈 API 호출 시 verify=False 적용
        response = requests.get(full_api_url, timeout=30, verify=False)
        response.raise_for_status() # HTTP 오류 발생 시 예외 발생
        print("API로부터 응답을 성공적으로 받았습니다.")
        api_data = response.json()

        with open(NEW_API_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(api_data, f, ensure_ascii=False, indent=4)
        print(f"API로부터 받은 원본 데이터를 '{NEW_API_DATA_FILE}' 파일에 저장했습니다.")
        print("-" * 30)
        print(f"알림: '{NEW_API_DATA_FILE}'의 데이터는 API 원본입니다. 지도에 사용하려면")
        print(f"'{JSON_FILE_PATH}' 파일처럼 'lat', 'lng', 'name', 'address', 'info' 필드를 포함하고,")
        print("올바른 형식으로 '가공'하는 작업이 필요합니다. ('/refresh' 주소에서 이 가공 과정을 수행합니다.)")
        print(f"현재 지도는 가공된 '{JSON_FILE_PATH}' 파일을 사용합니다.")
        print("-" * 30)
    except requests.exceptions.RequestException as e:
        print(f"청약홈 API 호출 중 오류 발생: {e}")
    except json.JSONDecodeError:
        print(f"청약홈 API 응답을 JSON으로 변환하는 데 실패했습니다. 응답 내용을 확인해주세요. 응답: {response.text[:200]}...") # 응답 일부 출력
    except Exception as e:
        print(f"API 데이터 처리 중 예상치 못한 오류 발생: {e}")

# --- 3. 웹사이트 라우트 설정 ---

@app.route('/')
def home():
    return """
    <h2>🏠 청약 지도 자동화 시스템</h2>
    <p><a href="/refresh">📦 [API 데이터 새로 받아와서 지도용 JSON 파일 생성]</a></p>
    <p><a href="/map">🗺️ [지도 보기]</a></p>
    <p>'/refresh' 주소로 접속하면 청약홈 API에서 최신 데이터를 받아와 주소 정보를 이용해 Kakao API에서 좌표를 가져온 후, 지도 표시를 위한 JSON 파일을 생성합니다.</p>
    <p>'/map' 주소로 접속하면 생성된 JSON 파일을 기반으로 지도를 표시합니다.</p>
    <p>JSON 파일 경로: <code>{}</code></p>
    """.format(JSON_FILE_PATH)

@app.route('/refresh')
def refresh_data():
    print("[API 업데이트 및 데이터 가공 시작]")

    try:
        api_url = f"https://api.odcloud.kr/api/ApplyhomeInfoDetailSvc/v1/getAPTLttotPblancDetail?page=1&perPage={API_PER_PAGE}&serviceKey={USER_SERVICE_KEY}"

        print(f"1. 청약홈 API ({api_url}) 데이터 가져오는 중...")
        # 청약홈 API 호출 (verify=False 적용)
        res = requests.get(api_url, timeout=20, verify=False)
        res.raise_for_status() # HTTP 상태 코드가 200번대가 아니면 예외 발생
        data = res.json()["data"] # "data" 키 아래에 실제 목록 데이터가 있음
        print(f"   -> 총 {len(data)} 건의 청약 데이터 확보.")

        if not data:
            return "❌ 오류 발생: 청약홈 API로부터 데이터를 받아오지 못했습니다."

        df = pd.DataFrame(data)

        # 필요한 컬럼 이름 통일
        df["address"] = df["HSSPLY_ADRES"]
        df["name"] = df["HOUSE_NM"]
        # 날짜 형식 변환 및 에러 처리
        df["모집공고일"] = pd.to_datetime(df["RCRIT_PBLANC_DE"], errors='coerce').dt.date
        df["공급규모"] = df["TOT_SUPLY_HSHLDCO"]

        # 초기값 설정 (API에 없는 정보는 '-'로 표시)
        df["APT 분양가"] = "-"
        df["발코니 분양가"] = "-"
        df["APT 평당가"] = "-"
        df["APT+발코니 평당가"] = "-"
        df["계약조건"] = "-"
        # 분양가상한제 Y/N 값을 '적용'/'미적용'으로 변환
        df["분양가상한제"] = df["PARCPRC_ULS_AT"].apply(lambda x: "적용" if x == "Y" else "미적용")

        # Kakao API를 사용하여 주소로 좌표(위도, 경도)를 가져오는 함수
        def get_coords(address):
            headers = {"Authorization": f"KakaoAK {KAKAO_KEY}"}
            api_endpoint = "https://dapi.kakao.com/v2/local/search/address.json"
            try:
                # --- Kakao API 호출 시 verify=False 적용 ---
                r = requests.get(api_endpoint, headers=headers, params={"query": address}, verify=False)
                # -----------------------------------------
                r.raise_for_status() # HTTP 오류 발생 시 예외 발생
                response_data = r.json()

                if response_data["documents"]:
                    # 첫 번째 검색 결과의 위도(y)와 경도(x) 반환
                    return response_data["documents"][0]["address"]["y"], response_data["documents"][0]["address"]["x"]
                else:
                    # 검색 결과가 없는 경우
                    #print(f"   -> Kakao API: '{address}' 주소 검색 결과 없음")
                    return None, None
            except requests.exceptions.RequestException as e:
                # 네트워크 오류, 타임아웃, HTTP 오류 등
                print(f"   -> Kakao API 호출 오류 ({address}): {e}")
                return None, None
            except json.JSONDecodeError:
                # API 응답이 유효한 JSON 형식이 아닌 경우
                print(f"   -> Kakao API: 응답 JSON 디코딩 오류 ({address})")
                #print(f"   -> 응답 내용: {r.text[:200]}...") # 응답 내용 일부 출력 (디버깅용)
                return None, None
            except Exception as e:
                # 그 외 예상치 못한 오류
                 print(f"   -> Kakao API 처리 중 예상치 못한 오류 ({address}): {e}")
                 return None, None


        features = []
        print("2. 각 주소별 좌표(위도, 경도) 가져오는 중...")
        # 데이터프레임의 각 행을 반복하며 좌표 가져오기
        # 데이터 양이 많을 경우 시간이 오래 걸릴 수 있습니다.
        total_rows = len(df)
        for index, row in df.iterrows():
            address_to_search = row["address"]
            # 진행 상황 출력 (선택 사항)
            #if (index + 1) % 10 == 0 or (index + 1) == total_rows:
            #    print(f"   -> 진행률: {index + 1}/{total_rows} 처리 완료 ({row['name']})")

            lat, lng = get_coords(address_to_search)

            # Kakao API 사용량 제한 고려하여 호출 사이에 딜레이 추가 (필수)
            time.sleep(0.3) # 권장 딜레이 (정책 확인 필요)

            # 유효한 좌표를 가져온 경우에만 features 리스트에 추가
            if lat is not None and lng is not None:
                 # 정보 문자열 생성 (팝업에 표시될 내용)
                 info = f"""모집공고일: {row['모집공고일']}
세대수: {row['공급규모']}
분양가상한제: {row['분양가상한제']}
APT 분양가: {row['APT 분양가']}
발코니 분양가: {row['발코니 분양가']}
APT 평당가: {row['APT 평당가']}
APT+발코니 평당가: {row['APT+발코니 평당가']}
계약조건: {row['계약조건']}"""

                 features.append({
                    "name": row["name"],
                    "address": row["address"],
                    # Kakao API는 위도(y), 경도(x) 순서로 반환하므로 그대로 저장
                    "lat": lat,
                    "lng": lng,
                    "info": info
                 })
            else:
                 print(f"   -> '{row['name']}' ({row['address']}) 데이터의 좌표를 가져오지 못했습니다.")


        print(f"3. 가공된 데이터를 '{JSON_FILE_PATH}' 파일에 저장하는 중...")
        # 지도에서 사용할 JSON 파일 형식에 맞게 저장
        with open(JSON_FILE_PATH, "w", encoding="utf-8") as f:
            # JavaScript 파일로 사용될 수 있도록 변수 선언 형식으로 저장
            f.write("const aptData = ")
            json.dump(features, f, ensure_ascii=False, indent=2) # 한글 깨짐 방지, 들여쓰기 적용
            f.write(";") # JavaScript 변수 선언의 끝을 표시

        print(f"   -> 총 {len(features)} 건의 좌표 데이터가 포함된 파일 저장 완료!")
        print("[API 업데이트 및 데이터 가공 완료]")
        return f"✅ 최신 데이터를 받아 {len(features)}건 저장 완료!<br><a href='/map'>[지도 보기]</a>"

    except requests.exceptions.RequestException as e:
        # 청약홈 API 호출 단계에서 발생한 오류
        print(f"❌ 청약홈 API 호출 중 심각한 오류 발생: {e}")
        return f"❌ 청약홈 API 호출 중 오류 발생: {e}"
    except KeyError as e:
         # API 응답 구조가 예상과 다를 때 발생하는 오류 (예: data 키 없음)
         print(f"❌ API 응답 데이터 구조 오류: 필요한 키 '{e}'를 찾을 수 없습니다.")
         return f"❌ API 응답 데이터 구조 오류: 필요한 키 '{e}'를 찾을 수 없습니다."
    except json.JSONDecodeError:
        print(f"❌ 청약홈 API 응답 JSON 디코딩 오류. 응답 내용을 확인하세요.")
        return f"❌ 청약홈 API 응답 JSON 디코딩 오류."
    except Exception as e:
        # 데이터 가공 또는 파일 저장 중 발생한 기타 오류
        print(f"❌ 데이터 처리 중 예상치 못한 심각한 오류 발생: {e}")
        return f"❌ 데이터 처리 중 예상치 못한 오류 발생: {e}"


@app.route('/map')
def show_map():
    print("[지도 생성 시작]")
    map_data_list = []
    try:
        print(f"1. '{JSON_FILE_PATH}' 파일 읽는 중...")
        # JSON 파일 읽기 (파일 시작의 'const aptData = '와 끝의 ';' 제거 필요)
        with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
            js_content_string = f.read().strip() # 앞뒤 공백 제거

        # 'const aptData = ' 접두사 제거
        prefix = 'const aptData = '
        if js_content_string.startswith(prefix):
            json_string = js_content_string[len(prefix):]
        else:
             json_string = js_content_string # 접두사가 없으면 그대로 사용 (오류 가능성 알림 필요)
             print(f"   -> 경고: '{JSON_FILE_PATH}' 파일이 'const aptData = '로 시작하지 않습니다.")


        # ';' 접미사 제거
        if json_string.endswith(';'):
            json_string = json_string[:-1]


        # JSON 문자열을 Python 리스트로 로드
        print("2. 파일 내용을 JSON 데이터로 변환 중...")
        map_data_list = json.loads(json_string)
        print(f"   -> 총 {len(map_data_list)} 건의 데이터 로드 완료.")

    except FileNotFoundError:
         print(f"❌ 오류 발생: '{JSON_FILE_PATH}' 파일을 찾을 수 없습니다.")
         return f"❌ 오류 발생: '{JSON_FILE_PATH}' 파일을 찾을 수 없습니다.<br>'/refresh' 주소로 접속하여 데이터를 먼저 받아오세요."
    except json.JSONDecodeError as e:
         print(f"❌ 오류 발생: '{JSON_FILE_PATH}' 파일의 JSON 형식이 잘못되었습니다: {e}")
         return f"❌ 오류 발생: '{JSON_FILE_PATH}' 파일의 JSON 형식이 잘못되었습니다.<br>파일 내용을 확인하거나 '/refresh'를 통해 다시 생성해보세요."
    except Exception as e:
        print(f"❌ 파일 로드 또는 JSON 변환 중 예상치 못한 오류 발생: {e}")
        return f"❌ 파일 로드 중 오류 발생: {e}"

    # 데이터가 없으면 지도 표시 대신 메시지 출력
    if not map_data_list:
        print("❌ 오류 발생: 지도에 표시할 데이터가 없습니다.")
        return f"❌ 오류 발생: 지도에 표시할 데이터가 없습니다.<br>'{JSON_FILE_PATH}' 파일에 좌표 데이터가 있는지 확인하거나 '/refresh'를 통해 데이터를 다시 받아오세요."


    print("3. Folium 지도를 생성하고 마커 추가 중...")
    # Folium 지도 객체 생성 (한국 대략적인 중앙 좌표, 초기 확대 레벨 설정)
    m = folium.Map(location=[36.5, 127.8], zoom_start=7)

    # 데이터 리스트를 순회하며 지도에 마커 추가
    processed_count = 0
    for item in map_data_list:
        # 딕셔너리에서 안전하게 데이터 가져오기 (키가 없어도 에러 발생 안 함)
        lat = item.get('lat')
        lng = item.get('lng')
        name = item.get('name', '이름 없음')
        address = item.get('address', '주소 없음')
        info = item.get('info', '')

        # 위도, 경도 값이 유효한 경우에만 마커 추가
        try:
            # lat, lng이 None이 아니고 float으로 변환 가능해야 함
            if lat is not None and lng is not None:
                folium.Marker(
                    # location은 [위도, 경도] 순서
                    location=[float(lat), float(lng)],
                    # 팝업 내용 설정 (HTML 태그 사용 가능, info 내용의 줄바꿈 \n을 <br>로 변경)
                    popup=folium.Popup(f"<h4><b>{name}</b></h4><b>주소:</b> {address}<hr>{info.replace('\\n', '<br>')}", max_width=400),
                    # 마커에 마우스를 올렸을 때 표시될 텍스트
                    tooltip=name
                ).add_to(m)
                processed_count += 1
            else:
                # 좌표가 유효하지 않은 데이터에 대한 경고 (선택 사항)
                print(f"   -> 경고: '{name}' ({address}) 데이터에 유효한 좌표(lat 또는 lng이 None)가 없어 마커를 건너뜁니다.")
        except (ValueError, TypeError):
             # lat 또는 lng 값이 숫자로 변환 불가능할 때의 오류 처리
             print(f"   -> 경고: '{name}' ({address}) 데이터의 lat/lng 값이 숫자가 아닙니다 (lat={lat}, lng={lng}). 마커를 건너뜁니다.")
             continue # 다음 데이터로 넘어감
        except Exception as e:
             # 마커 추가 중 예상치 못한 기타 오류
             print(f"   -> 경고: '{name}' 마커 추가 중 오류 발생: {e}")
             continue # 다음 데이터로 넘어감


    print(f"   -> 총 {processed_count} 건의 마커 추가 완료.")
    print("[지도 생성 완료]")
    # 생성된 지도를 HTML 형식으로 반환
    return m._repr_html_()

# --- 5. 웹사이트 실행! ---
if __name__ == '__main__':
    print(f"웹 애플리케이션 시작.")
    print(f"설정된 JSON 파일 경로: {JSON_FILE_PATH}")
    # 프로그램 시작 시 JSON 파일 존재 여부 확인
    if not os.path.exists(JSON_FILE_PATH):
        print(f"!!! 경고: 지정된 JSON 파일 경로에 파일이 존재하지 않습니다.")
        print(f"!!!     '{JSON_FILE_PATH}' 파일을 확인하거나, 웹 브라우저에서 '/refresh' 주소로")
        print(f"!!!     접속하여 파일을 먼저 생성해야 지도를 볼 수 있습니다.")
    else:
         print(f"JSON 파일 '{JSON_FILE_PATH}' 존재 확인.")

    print("\n웹 서버가 시작되었습니다.")
    print("웹 브라우저를 열고 다음 주소로 접속하세요:")
    print("  http://127.0.0.1:5000/")
    print("\nCtrl+C 를 눌러 서버를 종료하세요.")

    # Flask 개발 서버 실행
    # debug=True 설정 시 코드 변경 시 자동 재시작되며, 상세 에러 메시지 표시
    # 배포 시에는 debug=False로 설정해야 합니다.
    app.run(debug=True)