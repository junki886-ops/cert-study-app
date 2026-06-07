# 09. 모바일 앱처럼 사용하기

이 프로젝트는 Chrome 모바일에서 홈 화면에 추가해 앱처럼 열 수 있도록 PWA 설정을 포함합니다.

## 적용된 설정

- `static/manifest.webmanifest`: 앱 이름, 아이콘, 테마 색상, 표시 방식 설정
- `static/service-worker.js`: 정적 리소스 캐시용 service worker
- `static/icons/`: 홈 화면 아이콘
- `.streamlit/config.toml`: Streamlit 정적 파일 서빙 활성화
- `streamlit_app.py`: manifest, 아이콘, 모바일 메타태그 주입

## Android Chrome에서 설치하는 방법

1. Chrome에서 배포된 앱 주소로 접속합니다.
2. 오른쪽 위 메뉴를 누릅니다.
3. `홈 화면에 추가` 또는 `앱 설치`를 선택합니다.
4. 홈 화면에 `Cert Study` 아이콘이 생기면 실행합니다.

Hugging Face에서 확인할 때는 저장소 페이지가 아니라 실제 Space 실행 주소로 접속해야 합니다.

```text
https://Kentlo-cert-study-app.hf.space
```

아래 주소처럼 Hugging Face 저장소 화면에서 열면 Chrome은 Hugging Face 사이트를 보고 있는 것이므로 앱 설치 버튼이 기대한 대로 나오지 않을 수 있습니다.

```text
https://huggingface.co/spaces/Kentlo/cert-study-app
```

## 주의사항

- PWA 설치는 보통 HTTPS 환경에서 가장 안정적으로 동작합니다.
- 로컬 `http://localhost`에서는 테스트가 가능하지만, 실제 모바일 설치 확인은 배포 주소에서 하는 것이 좋습니다.
- Streamlit 앱 특성상 완전한 오프라인 문제풀이 앱은 아닙니다.
- 현재 service worker는 앱 전체 데이터를 오프라인 저장하지 않고, manifest와 아이콘 같은 정적 리소스만 캐시합니다.
- Chrome이 이전 manifest를 캐시할 수 있으므로 변경 직후에는 새로고침하거나 Chrome 사이트 데이터를 지운 뒤 다시 확인합니다.

## 확인할 것

Chrome 개발자도구의 Application 탭에서 아래 항목을 확인할 수 있습니다.

- Manifest
- Service Workers
- Cache Storage

Hugging Face Space나 Oracle Cloud 배포 후 모바일 Chrome에서 접속하면 홈 화면 추가를 테스트할 수 있습니다.
