from pathlib import Path
import json,hashlib
root=Path(__file__).resolve().parents[3]
out=Path(__file__).resolve().parent
result=json.loads((out/'POST_CLEANUP_CHECKS.json').read_text(encoding='utf-8'))
assert result['status']=='complete'
changes=[]
def edit(rel,fn):
    p=root/rel
    original=p.read_bytes()
    revised=fn(original.decode('utf-8').replace('\r\n','\n')).encode('utf-8')
    if revised!=original:
        p.write_bytes(revised)
        changes.append({'path':rel,'before_sha256':hashlib.sha256(original).hexdigest(),'after_sha256':hashlib.sha256(revised).hexdigest()})

summary=f"불필요한 제작 중간 파일 {result['removed_targets']}개 대상·{result['removed_files']}개 파일, 약 {result['removed_MiB']:.2f}MiB를 삭제했습니다. 삭제 직후 보존 파일 {result['protected_files_verified_unchanged']}개의 해시가 일치했습니다."
def start(t):
    insert='''**다음 세션 — PPT 완성 계속.** 사용자가 다음 작업을 최신 v5 PPT의 추가 완성으로 정했습니다. 새로 만들거나 설치부터 시작하지 않고 아래 ‘다음 발표 작업’ 순서로 이어갑니다. 오늘은 발표 자료·인계 정리까지 마쳤으며 새 앱·Pi 실험은 하지 않았습니다.

'''
    t=t.replace('**발표 내용 개선 — 2026-10-02.**',insert+'**발표 내용 개선 — 2026-10-02.**',1)
    old=next(l for l in t.splitlines() if l.startswith('> START_HERE.md'))
    t=t.replace(old,'> START_HERE.md → AGENTS.md의 최신 종료 절 → docs/SESSION_HANDOFF_2026-09-18.md 상단 → output/presentation/REFOUND_MIDTERM_FILL_GUIDE.md를 읽고 최신 v5 PPT를 이어서 완성해줘. 먼저 기존 내용과 발표 흐름을 검토하고 가능한 부분을 채워줘. 실제 캡처·성능·진행률은 근거가 있을 때만 반영하고, 마지막에 전체 화면과 한글 단어 중간 줄바꿈을 다시 확인해줘. 기존 PPT와 수동 수정본은 보존하고 설치·연결 방식 선정부터 반복하지 마.')
    t=t.replace('1. 위 **v5 개선본과 작성 가이드**를 열고 현재 내용을 함께 검토합니다. 기존 v3는 보존본입니다.','1. 위 **v5 개선본과 작성 가이드**에서 이어갑니다. 사용자가 다음 세션의 작업으로 PPT 추가 완성을 선택했습니다. 본문 흐름·설명·발표에 필요한 근거를 먼저 검토하고 기존 v3·v4와 수동 수정본은 보존합니다.')
    t=t.replace('3. **9쪽 공식 진행률과 19쪽 정량 결과**는 기준·측정 근거가 생긴 뒤 반영합니다. 현재는 미확정·미측정으로 표시했습니다.','3. **9쪽 공식 진행률과 19쪽 정량 결과**는 기준·측정 근거가 생긴 뒤 반영합니다. 현재는 미확정·미측정입니다. 25·26쪽의 세부 계획·역할은 제안이며, 3회 리허설·40건 파일럿은 수행 실적이 아닙니다.\n4. 최종 수정 후 전체 슬라이드를 렌더링해 한글 단어 중간 줄바꿈·잘림·넘침·연결선을 다시 확인하고 새 파일명으로 저장합니다. 실제 시연 연결을 할 때만 핫스팟 가이드를 참고합니다.')
    t=t.replace('실제 화면 4곳과 Git 이력 1곳, 공식 진행률·정량 성능은 채울 자리로 남겼습니다. 다음에는 위 가이드로 캡처를 채우거나 시연 준비를 이어가면 됩니다.','최신 v5에는 실제 Git 표와 출처를 표시한 개발 검사 화면을 넣었습니다. 다음 세션은 PPT 추가 완성이며 실제 Pi 캡처 교체·공식 진행률·정량 성능은 근거가 생기면 보완합니다.')
    return t+'\n## 2026-10-02 종료 정리\n\n'+summary+' 최종 v3·v4·v5 PPT, 생성 원본, 최종 렌더와 검사 로그, 화면 소스·코드·기존 데이터는 보존했습니다. 삭제 대상은 첫 검토용 렌더·초안 PPT·임시 차트 파일·일회성 문서 갱신 스크립트입니다. 별도로 삭제할 캐시·더미 데이터 폴더는 확인되지 않았습니다. 정리 기록은 `output/maintenance/2026-10-02-session-close/`입니다. 이번 변경은 아직 커밋하지 않았습니다.\n'
edit('START_HERE.md',start)

closure='''## 최신 종료·다음 세션 — 2026-10-02

- **사용자 지정 다음 작업은 PPT 추가 완성이다.** 최신 `output/presentation/REFOUND_PROJECT_MIDTERM_2026-10-02_v5_improved.pptx`에서 이어간다. 기존 목적·분량 위임·목차·수업 일정을 처음부터 다시 묻거나 새 PPT를 처음부터 만들지 않는다. 이번 종료 요청으로 새 PPT·앱 기능·Pi 시험을 시작하지 않았다.
- 읽기 순서는 `START_HERE.md` → 이 최신 절 → `docs/SESSION_HANDOFF_2026-09-18.md` 상단 → `output/presentation/REFOUND_MIDTERM_FILL_GUIDE.md`다. 실제 연결을 할 때 핫스팟 가이드를 추가로 읽는다. 미확인 실기를 발표 작업의 선행 조건으로 강제하지 않는다.
- **재개 순서:** 최신 v5의 내용·발표 흐름 검토 → 확보 가능한 근거 보완 → 실제 자료가 생기면 14·15쪽 Pi 캡처, 9쪽 공식 진행률, 19쪽 AI 정량 결과 교체 → 전체 렌더와 한글 단어 중간 줄바꿈·잘림·넘침 최종 확인. 25·26쪽 세부 일정·역할은 제안이며 3회 리허설·40건 파일럿을 완료 실적으로 쓰지 않는다.
- v5는 30장(본문 27·보충 3), 원본은 `docs/presentation/midterm/build_midterm_v5.mjs`다. 수동 편집본이 있으면 먼저 확인해 새 이름으로 보존한다. 생성 원본의 이미지 의존성인 `output/maintenance/2026-10-02-midterm-review/assets/detail.png`와 기존 개발 검사 PNG, 각 build 폴더의 `korean_typography.py`를 보존했다.
- '''+summary+''' 별도 캐시·더미 데이터 폴더는 없었으며, 이번 PPT의 임시 차트 디렉터리·첫 검토용 렌더·초안·일회성 문서 수정 스크립트만 제거했다. 최종 v3·v4·v5, 생성 원본·검사 로그·최종 렌더·소스·데이터는 보존했다.
- 정리 원장은 `output/maintenance/2026-10-02-session-close/cleanup-plan.json`, `cleanup-execution.json`, `POST_CLEANUP_CHECKS.json`, `SESSION_STATUS.json`이다. 제작 당시 `FINAL_CHECKS.json`은 그대로 보존한다. `check_final.py`의 첫 검토 렌더 비교는 삭제된 중간 경로를 필요로 하므로 종료 후 그대로 재실행하지 않는다. 삭제 전 파일 해시와 최종 렌더 보존은 종료 원장으로 확인한다.
- 앱·Pi·AI·SMTP 검사를 다시 수행하지 않았고 논문·배포·운영 데이터를 바꾸지 않았다. 이번 발표·문서 변경은 미커밋이며 commit/push는 수행하지 않았다. 아래 v3·v4 기본 재개와 이전 미확인 정리 기록보다 이 절이 우선한다.

'''
edit('AGENTS.md',lambda t:t.replace('## 최신 내용 개선 — 2026-10-02 후속',closure+'## 내용 개선 — 2026-10-02 후속',1))

handoff='''**2026-10-02 종료·재개 확정:** 사용자는 다음 세션에 **최신 v5 PPT를 이어서 완성**하기로 했다. 먼저 v5와 [작성·캡처 가이드](../output/presentation/REFOUND_MIDTERM_FILL_GUIDE.md)를 검토하고 설명·발표 흐름을 보완한다. 실물 자료가 생기면 14·15쪽 실제 Pi 화면, 9쪽 팀 기준 진행률, 19쪽 정량 AI 결과를 반영한다. 세부 역할·일정과 리허설 3회·파일럿 40건은 제안이다. 마지막에 전체 렌더와 한글 단어 중간 줄바꿈을 다시 확인한다. 기존 v3·v4·v5와 수동 편집본은 덮어쓰지 않는다. 새 설치·친구 응답·남은 실기를 발표의 선행 조건으로 강제하지 않는다.

'''+summary+''' 최종 PPT·렌더·제작 스크립트·화면 소스·검사 로그·기존 소스와 데이터는 보존했다. 정리 결과는 `output/maintenance/2026-10-02-session-close/SESSION_STATUS.json`을 따른다. 첫 검토용 렌더는 정리했으므로 과거 `check_final.py`의 해당 비교는 삭제 전 해시와 종료 검사 원장으로 대체한다. 이번에는 앱·Pi·AI 실험, 커밋·push를 하지 않았다.

'''
edit('docs/SESSION_HANDOFF_2026-09-18.md',lambda t:t.replace('\n\n','\n\n'+handoff,1).replace('**최종 갱신: 2026-09-30.**','**이전 동기화 기록: 2026-09-30.**',1).replace('아래 상태가 과거 인계보다 우선한다.','현재 우선순위는 위 10월 2일 종료·재개 기록을 따른다.',1))

edit('docs/IMPROVEMENTS.md',lambda t:t.replace('다음 작업은 v5 개선본 검토와 실제 Pi 캡처 보완입니다.','사용자가 정한 다음 세션 작업은 v5 PPT 추가 완성입니다. 내용·발표 흐름을 검토하고 실제 Pi 캡처·측정 근거를 확보하면 보완합니다. 마지막에 전체 화면과 한글 단어 중간 줄바꿈을 다시 검토합니다.',1))
edit('output/presentation/REFOUND_MIDTERM_FILL_GUIDE.md',lambda t:t.replace('\n\n','\n\n**다음 세션 작업 확정 — 2026-10-02 종료:** 최신 v5에서 PPT 추가 완성을 이어갑니다. 아래 근거·캡처 보완 순서를 따르고, 수정 후 전체 슬라이드의 한글 단어 중간 줄바꿈·넘침을 다시 확인합니다. 실제 Pi 연결이나 새 측정은 자료 보완에 필요할 때 별도로 진행합니다.\n\n',1)+'\n## 세션 종료 후 제작 파일\n\n최종 v3·v4·v5와 최종 PowerPoint 렌더·생성 스크립트·화면 소스·검증 로그를 보존했습니다. 이번 제작의 초안·첫 검토 렌더·임시 차트 파일은 정리했습니다. 기존 `FINAL_CHECKS.json`은 제작 당시 기록이며 정리 이후의 보존 확인은 `output/maintenance/2026-10-02-session-close/POST_CLEANUP_CHECKS.json`을 따릅니다. 다음 수정은 v5 생성 원본 또는 수동 수정본을 기준으로 **새 출력 이름**을 사용합니다.\n')
(out/'documentation-changes.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2),encoding='utf-8')
print(f'Updated {len(changes)} handoff documents.')
