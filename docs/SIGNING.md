# Developer ID 서명·공증 릴리스 운영 안내

`shotsort`의 공개 DMG는 Developer ID Application 서명과 Apple notarization을 거친 뒤 배포한다. 인증서, private key, Apple ID 또는 앱 전용 비밀번호는 저장소에 넣지 않는다.

## 최초 준비

1. Apple Developer Program에서 **Developer ID Application** 인증서를 만들고, private key를 포함한 `.p12`를 export한다.
2. GitHub repository secrets에 아래 값을 추가한다.
   - `SIGN_IDENTITY`: 예: `Developer ID Application: Example, Inc. (TEAMID)`
   - `APPLE_CERTIFICATE_P12_BASE64`, `APPLE_CERTIFICATE_PASSWORD`
   - `APPLE_ID`, `APPLE_TEAM_ID`, `APPLE_APP_SPECIFIC_PASSWORD`
   - 선택: `KEYCHAIN_PASSWORD` (없으면 runner가 일회용 값을 만든다)
3. workflow가 macOS 임시 keychain에 인증서를 import하고 `shotsort-notary` notarytool profile을 만든다. job 종료 뒤 runner와 함께 폐기된다.

## 릴리스

검증을 마친 커밋에 `v*` 태그를 push하면 `Notarized DMG release` workflow가 실행된다. secret이 하나라도 없으면 asset을 만들기 전에 실패하며, 무서명 DMG를 릴리스하지 않는다.

workflow 순서는 `.app` 빌드 → hardened runtime 서명 → DMG 생성 → notarization → staple → checksum → clean-install smoke → GitHub Release 업로드다. `build_app.sh`를 로컬에서 서명하려면 `SIGN_IDENTITY`와 `NOTARY_PROFILE`을 반드시 함께 설정한다. 둘 다 생략한 로컬 빌드는 개발 확인 전용이며 배포할 수 없다.

## 다운로드 검증

릴리스에서 `shotsort.dmg`와 `shotsort.dmg.sha256`를 함께 내려받아 macOS에서 실행한다.

```bash
shasum -a 256 -c shotsort.dmg.sha256
```

출력이 `OK`이면 DMG를 열고 앱을 Applications로 끌어 놓는다. Gatekeeper가 정상 검증하는 공증 릴리스에서는 우회 명령이 필요 없다.

## smoke와 최종 점검

CI smoke는 새 임시 mountpoint에 DMG를 attach해 임시 Applications 폴더로 복사하고, 복사본의 `codesign`, Gatekeeper(`spctl`), staple 검증을 한다. 실제 `/Applications`, 사용자 홈, 앱 실행은 건드리지 않는다.

출시 전에는 별도 새 macOS 사용자 계정에서도 DMG를 내려받아 설치·첫 실행·업데이트 링크를 한 번 확인한다.
