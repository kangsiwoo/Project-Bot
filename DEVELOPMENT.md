# 🚀 개발 빠른 시작 가이드

Project-Bot 개발을 위한 빠른 참고 가이드입니다. 자세한 내용은 [CONTRIBUTING.md](CONTRIBUTING.md)를 참고하세요.

## 💡 30초 요약

1. **브랜치 생성**: `git checkout -b feature/your-feature-name`
2. **개발**: 기능을 구현하고 자주 커밋 (`git commit`)
3. **푸시**: `git push origin feature/your-feature-name`
4. **PR 생성**: GitHub에서 PR을 열고 템플릿 작성
5. **리뷰 대기**: 팀원들의 리뷰를 기다림
6. **병합**: 모든 리뷰가 승인되면 머지

---

## 📝 커밋 메시지 예시

```bash
# 기본 형식
git commit -m "feat(기능명): 설명"

# 예시
git commit -m "feat(auth): JWT 토큰 검증 기능 추가"
git commit -m "fix(api): 사용자 조회 에러 수정"
git commit -m "docs: README 업데이트"
```

---

## 🔄 워크플로우 체크리스트

### 개발 시작
- [ ] `git pull origin main` (최신 main 동기화)
- [ ] `git checkout -b feature/your-feature` (브랜치 생성)

### 개발 중
- [ ] 기능별로 `git commit` (최소 2개 이상)
- [ ] `git push origin feature/your-feature` (정기적으로 푸시)
- [ ] 테스트 코드 작성

### ⚠️ PR 제출 (이슈당 PR 하나)
**중요: 1 Issue = 1 PR 원칙을 반드시 따르세요!**
- [ ] 관련 이슈가 있는지 확인 (없으면 먼저 이슈 생성)
- [ ] PR 템플릿에 맞춰 설명 작성
- [ ] 관련 이슈 링크 (`Closes #123`)
- [ ] 체크리스트 모두 확인

### 리뷰 후 병합
- [ ] 모든 피드백 반영
- [ ] CI/CD 통과
- [ ] 승인된 후 머지
- [ ] 로컬 브랜치 삭제: `git branch -d feature/your-feature`

---

## 🏷️ 브랜치 명명 규칙

| 타입 | 형식 | 예시 |
|------|------|------|
| 기능 | `feature/...` | `feature/user-auth` |
| 버그 | `bugfix/...` | `bugfix/login-error` |
| 리팩토링 | `refactor/...` | `refactor/api-layer` |
| 문서 | `docs/...` | `docs/setup-guide` |

---

## 📋 커밋 타입

| 타입 | 설명 | 예시 |
|------|------|------|
| `feat` | 새로운 기능 | `feat(auth): 로그인 구현` |
| `fix` | 버그 수정 | `fix(api): 에러 처리 개선` |
| `docs` | 문서 작성 | `docs: API 문서 추가` |
| `style` | 코드 포맷 | `style: 코드 정렬` |
| `refactor` | 리팩토링 | `refactor: 함수 추출` |
| `test` | 테스트 | `test: 단위 테스트 추가` |
| `chore` | 기타 작업 | `chore: 패키지 업데이트` |

---

## ⚠️ 주의사항

### 하면 안 되는 것

❌ `main` 브랜치에서 직접 개발
❌ 파일 하나에 여러 기능을 섞어서 커밋
❌ 리뷰 없이 병합
❌ 의미 없는 커밋 ("수정", "작업 중" 등)

### 권장되는 것

✅ 기능마다 브랜치 분리
✅ 작은 단위의 의미있는 커밋
✅ PR 템플릿 필수 사용
✅ 코드 리뷰 적극 활용

---

## 🆘 트러블슈팅

### 잘못된 브랜치에 커밋했을 때

```bash
# 마지막 커밋만 취소
git reset --soft HEAD~1

# 새로운 브랜치에서 커밋
git checkout -b correct-branch
git commit -m "message"
```

### 최신 main을 내 브랜치에 반영하고 싶을 때

```bash
git fetch origin
git rebase origin/main
```

### PR을 새로 시작하고 싶을 때

```bash
# 현재 브랜치의 모든 변경사항 버림
git reset --hard origin/main
```

---

## 📚 자세한 정보

- [CONTRIBUTING.md](CONTRIBUTING.md) - 전체 개발 가이드
- [.github/pull_request_template.md](.github/pull_request_template.md) - PR 템플릿
- [.github/commit_template.md](.github/commit_template.md) - 커밋 템플릿

---

**Happy Coding! 🎉**
