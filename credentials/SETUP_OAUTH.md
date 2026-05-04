# 구글 스프레드시트 연동을 위한 OAuth 설정 가이드 (개발자용)

> 이 문서는 **프로그램을 배포·관리하는 사람**이 한 번만 수행하면 되는 작업입니다.
> 일반 사용자는 이 문서를 볼 필요가 없습니다.

기본값(로컬 CSV 저장)으로도 모든 기능이 동작합니다. 구글 시트 연동을 켜고 싶을 때만 아래 절차를 진행하세요.

---

## 1. Google Cloud Console에서 OAuth 클라이언트 ID 발급

### 1-1. 프로젝트 생성

1. https://console.cloud.google.com 접속 (구글 계정 로그인)
2. 상단 좌측 프로젝트 선택 드롭다운 → **새 프로젝트**
3. 이름: `fee-manager` (아무 이름이나 가능) → **만들기**

### 1-2. API 활성화

1. 좌측 햄버거 메뉴 → **API 및 서비스 > 라이브러리**
2. 검색창에 `Google Sheets API` 입력 → 클릭 → **사용 설정**
3. 다시 라이브러리로 돌아와서 `Google Drive API` 도 같은 방법으로 **사용 설정**

### 1-3. OAuth 동의 화면 구성

1. 좌측 메뉴 → **API 및 서비스 > OAuth 동의 화면**
2. User Type: **외부** 선택 → **만들기**
3. 앱 이름: `회비관리` (사용자에게 보여질 이름)
4. 사용자 지원 이메일, 개발자 연락처 이메일: 본인 이메일
5. 나머지는 기본값으로 두고 **저장 후 계속**
6. 범위(scopes): **저장 후 계속** (추가 X)
7. 테스트 사용자: **Add Users** 버튼 → 본인 이메일 + 실제 사용자들 이메일 추가
   - 이 단계가 중요. 여기 등록된 이메일만 로그인 가능 (앱이 "테스트 모드"라서)
   - 사용자가 늘어나면 여기에 계속 추가하거나, 나중에 앱 게시 신청
8. **저장 후 계속**

### 1-4. OAuth 클라이언트 ID 만들기

1. 좌측 메뉴 → **API 및 서비스 > 사용자 인증 정보**
2. 상단 **+ 사용자 인증 정보 만들기** → **OAuth 클라이언트 ID**
3. 애플리케이션 유형: **데스크톱 앱**
4. 이름: `fee-manager-desktop`
5. **만들기**
6. 팝업에서 **JSON 다운로드** 클릭

### 1-5. 다운받은 파일을 프로젝트에 배치

다운받은 파일 (예: `client_secret_xxx.googleusercontent.com.json`) 을
다음 위치에 **`client_secret.json`** 이라는 이름으로 저장:

```
fee_manager/credentials/client_secret.json
```

---

## 2. 코드 활성화

`src/auth.py` 를 열고 `get_gspread_client()` 함수의 주석 처리된 참고 구현을
실제 코드로 교체하세요. 함수 안의 docstring 에 그대로 사용 가능한 코드가 있습니다.

핵심은 `NotImplementedError` 를 제거하고 그 자리에 다음을 넣는 것:

```python
import gspread
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

creds = None
if TOKEN_FILE.exists():
    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file(
            str(CLIENT_SECRET_FILE), SCOPES
        )
        creds = flow.run_local_server(port=0)
    TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
return gspread.authorize(creds)
```

또한 `src/sheets_storage.py` 의 각 메서드를 실제 gspread API 호출로 채워야 합니다.
(현재는 `NotImplementedError` 가 들어있는 스켈레톤 상태)

---

## 3. 첫 실행

1. `run.bat` 더블클릭
2. 설정 페이지에서 백엔드를 **구글 스프레드시트** 로 변경
3. 빈 구글 시트를 하나 만들고, URL 의 `/d/` 다음 부분(스프레드시트 ID)을 설정에 입력
4. 저장 시 브라우저가 열리면서 구글 로그인 화면 → 본인 계정 선택
5. "확인되지 않은 앱입니다" 경고가 뜨면 → **고급 > 안전하지 않은 페이지로 이동**
   (테스트 모드라서 그런 것이며, 위험하지 않음)
6. 권한 허용 → 토큰이 `credentials/token.json` 에 저장됨
7. 다음 실행부터는 자동 로그인

---

## 4. 다른 사용자에게 배포할 때

- `credentials/client_secret.json` 은 함께 배포해도 무방합니다 (OAuth 클라이언트 ID는 비밀이 아님)
- `credentials/token.json` 은 사용자별로 다르므로 절대 함께 배포하지 마세요 (.gitignore 됨)
- OAuth 동의 화면의 **테스트 사용자** 목록에 새 사용자 이메일을 미리 추가해야 함
- 사용자가 많아지면 OAuth 동의 화면에서 "앱 게시 신청" → 구글 검수 받으면 누구나 사용 가능

---

## 트러블슈팅

| 증상 | 원인 / 해결 |
|---|---|
| `redirect_uri_mismatch` 오류 | 데스크톱 앱이 아니라 웹 앱으로 만든 경우. OAuth 클라이언트 ID 다시 생성 |
| `access_denied` 오류 | OAuth 동의 화면의 테스트 사용자에 해당 이메일이 없음 |
| `invalid_grant` 오류 | `token.json` 만료/손상. 파일 삭제 후 재로그인 |
| 시트가 보이지 않음 | drive.file 스코프는 "프로그램이 만든/연 시트만" 접근. 기존 시트도 한 번 프로그램에서 열어야 함 |
