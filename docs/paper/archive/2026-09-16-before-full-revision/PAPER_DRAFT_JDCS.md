# 저사양 엣지 장치에서의 사건 기반 장면 변화 감지와 선택적 멀티모달 추론을 이용한 분실물 관리 시스템

> 문서 상태: JDCS 투고용 1차 전체 초안  
> 작성 기준: 2026-09-15 현재 저장소 코드와 루트 README  
> 중요한 표시: 이중 대괄호로 감싼 항목은 실험 또는 서지 확인 후 반드시 교체해야 하는 값이다.  
> 분량 상태: 누락 방지를 위한 장문 원고이므로, 결과 입력 후 중복 설명과 보조 표를 부록으로 옮겨 JDCS 양식 9~10쪽으로 압축한다.  
> 심사용 원고에서는 저자·소속·감사의 글을 삭제하고, 아래 “편집 메모”도 제거한다.

## 원고 메타데이터

- 국문 제목: 저사양 엣지 장치에서의 사건 기반 장면 변화 감지와 선택적 멀티모달 추론을 이용한 분실물 관리 시스템
- 영문 제목: An Event-Triggered Scene Change Detection and Selective Multimodal Inference System for Lost-Item Management on a Resource-Constrained Edge Device
- 저자 후보: 장진석, 권기원
- 저자 순서·교신저자: [[AUTHOR_ORDER_AND_CORRESPONDING]]
- 소속 후보: 동양미래대학교 인공지능소프트웨어학과
- 투고 목표: 디지털콘텐츠학회논문지(JDCS)
- 원고 성격: 시스템 설계·구현 및 실험적 검증

---

## 국문 초록

고정 카메라 기반 분실물 자동 등록은 다양한 물품을 다뤄야 할 뿐 아니라 자동 노출, 그림자, 초점 변화와 미세진동 때문에 저사양 장치에서 안정적으로 동작하기 어렵다. 본 논문은 Raspberry Pi 4 2GB에서 움직임 종료와 장면 안정화를 확인한 뒤 영상 정합, 전역·국소 조명 보정, 지속 경계 억제 및 활성 물품 대응으로 추가·이동·제거를 선별하는 Re:Found를 제안한다. 신규 등록과 제거가 모호한 경우에만 전후 전체 장면 및 후보 crop 최대 4장을 외부 멀티모달 모델에 보낸다. callback worker가 정상 접수한 신규 등록은 응답 전 임시 레코드로 저장하고, 제거 검증 중에는 기존 물품을 유지한다. [[N_EVAL_EPISODES]]개 평가 episode에서 로컬 Macro-F1은 [[LOCAL_MACRO_F1]], 연속 무사건 오탐률은 [[FALSE_EVENTS_PER_HOUR]]건/시간, Raspberry Pi 처리 지연 p50/p95는 [[LOCAL_LATENCY_P50_MS]]/[[LOCAL_LATENCY_P95_MS]] ms였다. 외부 호출률은 [[VLM_CALL_RATE]], 종단간 업무 성공률은 [[END_TO_END_TASK_SUCCESS]]였으며, [[ABSTRACT_KO_CONCLUSION]].

**주제어:** 엣지 컴퓨팅, 장면 변화 감지, 멀티모달 인공지능, 분실물 관리, 라즈베리 파이

## Abstract

Automated lost-item registration with a fixed camera must handle open-ended object categories while remaining robust to exposure shifts, cast shadows, autofocus breathing, and slight camera displacement on limited hardware. This paper presents Re:Found, an event-triggered lost-item management system implemented on a Raspberry Pi 4 with 2 GB of memory. After motion has ceased and the scene has remained stable, the edge pipeline performs geometric alignment, global and local illumination compensation, persistent-edge jitter suppression, and association with active items. It emits added, moved, and removed events locally. Only a newly added item or an ambiguous removal is sent to an external multimodal model using at most four pieces of evidence: full-scene before/after images and high-resolution candidate crops. For an added event accepted by the callback worker, a provisional record is committed before remote inference; an ambiguous removal leaves the existing record active until verification. In [[N_EVAL_EPISODES]] evaluation episodes, the local detector achieved a macro-F1 of [[LOCAL_MACRO_F1]] and [[FALSE_EVENTS_PER_HOUR]] false events per hour during continuous no-event monitoring. Median and 95th-percentile local processing latencies were [[LOCAL_LATENCY_P50_MS]] and [[LOCAL_LATENCY_P95_MS]] ms. The selective policy invoked remote inference for [[VLM_CALL_RATE]] of episodes, and the end-to-end task success rate was [[END_TO_END_TASK_SUCCESS]]. These results demonstrate [[ABSTRACT_EN_CONCLUSION]].

**Keywords:** Edge Computing, Scene Change Detection, Multimodal AI, Lost-Item Management, Raspberry Pi

---

# 1. 서론

학교, 도서관과 공공시설의 분실물 업무는 물품의 접수, 분류, 보관, 만료 알림과 회수 이력을 함께 관리해야 한다. 기존의 수기 등록은 담당자의 반복 입력을 요구하고, 사진 기반 등록 시스템도 사용자가 촬영과 업로드를 수행해야 사건이 생성된다[1]. 감시 영상에서 사람과 소지품을 추적하는 방법은 소유 관계나 유기 상황을 분석하는 데 적합하지만[2], 저사양 보관대 카메라에서 모든 프레임에 객체 탐지와 추적을 수행하면 연산량과 학습 클래스 범위가 문제가 된다.

분실물 보관대의 핵심 관찰 대상은 사람의 행동 자체보다 “안정된 장면에서 어떤 물품이 생기고, 이동하고, 사라졌는가”이다. 그러나 고정형 카메라도 완전히 고정된 센서는 아니다. 자동 노출과 색온도, 국소 조명과 그림자, 초점 호흡, 설치대 진동이 전후 영상의 넓은 영역이나 기존 경계에 차이를 만든다. 단순 차영상은 이 차이를 새 물품으로 오인할 수 있고, 반대로 바닥과 휘도가 유사한 물품은 놓칠 수 있다. 차량 내 탑승 전·후 영상을 비교한 경량 연구[3]는 Raspberry Pi에서 전후 차분의 가능성을 보였지만, 연속 감시 상태 전이, 같은 물품의 이동과 제거 구분, 개방형 물품 설명 및 업무 데이터 보존까지는 다루지 않았다.

한편 외부 멀티모달 모델은 고정된 소수 클래스에 한정되지 않고 물품명, 외형과 범주를 설명할 수 있으나 모든 프레임을 전송하는 방식은 네트워크 의존성, 지연, 비용과 개인정보 노출 범위를 키운다. 이에 본 연구는 엣지 장치가 의미를 직접 분류하기보다 변화 사건을 안정적으로 선별하고, 의미 판단이 필요한 증거만 외부 모델에 전달하는 역할 분리를 채택한다. callback worker가 정상 접수한 added 사건은 원격 응답 전에 임시 물품으로 저장하여 이후 외부 서비스 실패에도 관찰을 확인할 수 있게 하고, verify_removed는 기존 물품을 유지한 채 원격 검증한다.

본 연구의 질문은 다음과 같다.

- RQ1. 안정 장면에서 물품 추가, 이동과 제거를 어느 정도 정확하게 검출할 수 있는가?
- RQ2. 영상 정합, 전역 노출 보정, 지속 경계 흔들림 억제와 국소 조명 보정은 방해요인 오탐을 얼마나 줄이는가?
- RQ3. Raspberry Pi 4 2GB에서 로컬 처리의 지연, 처리율, CPU, 메모리와 온도는 어느 수준인가?
- RQ4. 사건을 로컬에서 선별한 뒤 멀티모달 추론을 선택적으로 호출할 때 최종 판단 성능, 호출률과 전송량은 어떻게 달라지는가?

본 논문의 기여는 다음 네 가지이다.

1. 움직임 종료와 안정 구간을 명시적으로 구분하고, 기하 정합·조명 보정·경계 흔들림 억제를 결합한 저사양 고정 카메라용 사건 검출 파이프라인을 설계·구현하였다.
2. 등록 당시의 물품 crop과 빈 배경 crop을 이용하여 추가, 이동, 제거 및 제거 검증 사건을 구분하고, 이동 시 기존 물품 ID를 유지하는 로컬 대응 절차를 구현하였다.
3. 전체 장면 전·후와 후보 crop 전·후를 최대 4장의 방향성 있는 증거로 구성하여 신규 물품과 모호한 제거에만 멀티모달 추론을 적용하는 하이브리드 구조를 제시하였다.
4. 정상 접수된 added의 원격 추론 전 임시 저장, 경로별 현재 상태 재확인과 트랜잭션 기반 생명주기 갱신을 결합한 운영 구조를 구현하고, 장애 주입을 포함하는 재현 가능한 실험 스키마와 ablation 절차를 설계하였다.

본 연구는 새로운 특징 추출기나 학습 모델을 제안하지 않는다. 기여의 중심은 기존의 경량 영상처리 기법을 고정 카메라의 방해 조건에 맞게 단계화하고, 선택적 외부 의미 추론 및 분실물 생명주기와 통합한 시스템을 실제 저사양 장치에서 검증하는 데 있다.

# 2. 관련 연구

## 2-1. 분실물 및 방치 물체 감지

국내 유실물 관리 연구는 정적 이미지의 분류·검색과 감시 영상의 객체 추적이라는 두 방향으로 발전하였다. 정하민 등[1]은 사용자가 촬영한 단일 사진에서 카테고리와 태그를 추출하고 가중치 기반 검색 순위를 제공하였다. 이 방식은 등록과 조회 편의를 높였으나 유실 사건 자체는 사용자가 입력해야 한다. 장현상 등[2]은 YOLOv8, Deep OC-SORT와 BLIP을 결합하여 열차 영상에서 사람과 소지품을 추적·매칭하였다. 이는 소유자 관계 추적에 적합하지만 프레임별 딥러닝 추론과 대상 탐지 클래스를 전제로 한다.

본 연구와 장치 및 전후 영상 관점에서 가장 가까운 양형준과 최규상[3]은 Raspberry Pi 4에서 승객 탑승 전·하차 후 영상 30쌍을 MOG2, 히스토그램 평활화와 윤곽선 필터링으로 비교하였다. 박혜승 등[4]은 이중 배경 차감과 Mask R-CNN을 이용해 등록 및 미등록 물체의 제거를 감지하였고, 류동균과 이재흥[5]은 차영상으로 후보 영역을 얻은 뒤 CNN으로 쓰레기 여부를 분류하였다. 이들 연구는 변화 영역을 먼저 찾고 의미를 나중에 판별한다는 공통점이 있으나, 연속 감시 중 추가·이동·제거를 하나의 물품 생명주기로 연결하거나 엣지와 외부 범용 의미 추론의 역할을 분리하지는 않았다.

김기현 등[6]은 YOLOv4와 Raspberry Pi를 결합한 쓰레기 분리배출 시스템을 구현하여 엣지 장치와 관리 서비스의 통합 사례를 보였다. 다만 해당 연구의 모델 학습과 성능 측정 환경은 GPU 서버이므로, 그 수치를 Raspberry Pi의 추론 성능으로 해석할 수 없다. 박승우 등[7]은 Raspberry Pi 4에서 여러 경량 객체 탐지 모델의 정확도, 속도와 전력을 비교하여 저사양 장치에서의 성능 절충을 제시하였다. Re:Found는 고정 클래스 객체 탐지기를 계속 실행하는 대신, 로컬에서는 의미와 무관한 변화 사건을 찾고 외부 모델은 선택된 사건만 설명한다.

## 2-2. 고정 카메라의 배경 유지와 영상 정합

고정 카메라 영상에서는 현재 영상과 배경 모델의 차이로 전경을 추출하는 방법이 널리 사용된다. Stauffer와 Grimson[8]은 각 화소를 적응형 가우시안 혼합으로 모델링하였고, Zivkovic[9]은 혼합 성분의 수를 적응적으로 조절하는 배경 차감 방법을 제시하였다. Wallflower[10]는 조명 변화, 움직인 배경 물체, 그림자와 초기화 같은 배경 유지의 대표적 실패 조건을 픽셀·영역·프레임 수준에서 다루었다. Lin 등[11]은 장·단기 배경과 화소 단위 유한상태기계를 이용하여 정지 전경과 방치 수하물을 판별하였다.

그러나 실제 고정 카메라 영상은 장착대 진동이나 초점 변화로 화소가 완전히 일치하지 않을 수 있다. Shi와 Tomasi의 특징점 선택[12], Lucas와 Kanade의 광류[13], Fischler와 Bolles의 RANSAC[14]은 대응점 기반 기하 보정의 기초를 제공한다. 본 연구는 안정 장면 사이에서 기준 영상의 특징점을 순방향과 역방향으로 추적하고, 장면 전체에 분산된 대응점만을 이용해 제한된 부분 affine 변환을 추정한다. 이후 전역·국소 조명 변화와 양쪽 영상에 지속되는 경계 흔들림을 순서대로 억제한다.

## 2-3. 엣지–클라우드 협력과 선택적 영상 분석

엣지 컴퓨팅은 센서와 가까운 위치에서 일부 처리를 수행하여 응답성과 연결 장애 대응을 높이는 구조이다[15]. Neurosurgeon[16]과 Edgent[17]는 심층 신경망 계산을 단말과 엣지 또는 클라우드에 분할하는 협력 추론을 다루었다. NoScope[18]는 고정 영상 질의를 위해 차이 검출기와 대상별 특화 모델을 cascade로 구성하였고, Reducto[19]는 자원이 제한된 카메라에서 저수준 특징으로 불필요한 프레임을 동적으로 선별하였다.

Re:Found도 경량 선별 후 고비용 추론을 수행한다는 점에서 이들과 같은 문제의식을 갖지만, DNN 계층을 분할하거나 특정 객체용 소형 모델을 학습하지 않는다. 대신 Raspberry Pi는 안정화된 물체 상태 변화와 기존 물품의 동일성 판단을 담당하고, 외부 멀티모달 모델은 선택된 전후 증거의 방향과 개방형 의미를 해석한다. BLIP-2[20]와 같은 시각–언어 모델은 이미지에서 자연어 의미를 연결할 가능성을 보였고, 권영환[21]은 BLIP-2를 유실물 어노테이션 증강에 적용하였다. 본 연구는 정적 어노테이션 생성이 아니라 실제 사건의 전체 장면과 crop 전후 맥락을 온라인 등록과 제거 검증에 사용한다.

**표 1. 관련 연구 비교 / Table 1. Comparison with related work**

| 연구 | 입력 및 방법 | 실행 구조 | 본 연구와의 차이 |
|---|---|---|---|
| 정하민 등[1] | 단일 사진, 계층형 분류·랭킹 | 서버 중심 | 사용자가 사건을 직접 등록 |
| 장현상 등[2] | YOLOv8, Deep OC-SORT, BLIP | 프레임별 딥러닝 | 사람–소지품 관계 중심 |
| 양형준·최규상[3] | 전후 30쌍, MOG2·윤곽선 | Raspberry Pi 4 | 연속 상태기계·이동 ID·VLM 없음 |
| 박혜승 등[4] | 이중 배경 차감, Mask R-CNN | 경량·고성능 두 방식 | 도난과 제거 감시 중심 |
| NoScope[18] | 차이 검출기와 특화 모델 cascade | 서버 영상 질의 | 대상별 특화 모델 학습 필요 |
| Reducto[19] | 저수준 특징 기반 프레임 필터 | 카메라–서버 | 사건 의미와 업무 생명주기 없음 |
| Re:Found | 정합·상태기계·활성 물품 대응, 선택적 VLM | Pi 4 2GB와 외부 API | 추가·이동·제거와 보관 생명주기 통합 |

표 1의 문헌들은 데이터셋, 클래스와 평가 단위가 서로 다르므로 각 논문의 F1, mAP 또는 정확도 수치를 본 연구 결과와 직접적인 우열로 비교하지 않는다.

# 3. 시스템 설계

## 3-1. 설계 목표

시스템의 설계 목표는 다음과 같다. 첫째, Raspberry Pi 4 2GB와 CSI 카메라만으로 연속 감시와 웹 서비스를 함께 실행한다. 둘째, 자동 노출, 그림자, 초점과 미세진동을 신규 물품으로 오인하지 않도록 안정 장면 단위로 판단한다. 셋째, 같은 물품이 화면 안에서 이동한 경우 새 물품 레코드를 만들지 않고 기존 ID를 유지한다. 넷째, 성공적으로 임시 저장된 로컬 관찰은 이후 외부 AI 또는 네트워크 실패만으로 삭제되지 않게 한다. 다섯째, 자동 결과가 불확실하면 신규 물품은 확인 필요 상태로 두고 기존 물품은 자동 전환하지 않는다.

## 3-2. 전체 구조

Re:Found는 엣지 영상처리, 선택적 의미 추론, 서비스 생명주기의 세 계층으로 구성된다. Raspberry Pi에 연결된 고정형 CSI 카메라 영상은 Picamera2[22]로 입력되고, OpenCV 기반 VisionMonitor가 움직임, 안정 상태와 장면 변화를 판정한다. 영상 수집 스레드와 사건 callback 스레드를 분리하여 데이터베이스와 네트워크 처리가 프레임 수집을 직접 정지시키지 않게 하였다.

로컬 단계가 생성하는 사건은 added, moved, removed, verify_removed와 경계상자로 구성된다. added와 verify_removed만 외부 멀티모달 모델에 전달하고, 식별이 명확한 moved와 removed는 로컬에서 처리한다. FastAPI 계층은 사건 조정, 관리자 REST API와 MJPEG 미리보기를 담당한다. SQLite WAL[23]은 물품, 활동, 알림과 설정을 저장하고, 물품 crop 및 빈 배경 crop은 파일 시스템에 저장한다. 외부 의미 추론은 설정에 따라 OpenAI Responses API[24] 또는 Gemini API[25]를 사용한다. 최종 물품은 stored, due, recovered, disposed 상태로 관리되고, 분류별 보관 기한과 알림, 회수·폐기·복원 이력이 같은 서비스에 연결된다.

[[FIGURE_1_SYSTEM_ARCHITECTURE]]

**그림 1. Re:Found의 전체 시스템 구조 / Fig. 1. Overall architecture of Re:Found**

편집 지시: 카메라→로컬 사건 검출→FastAPI/SQLite→선택적 VLM→관리자 화면 구조도를 삽입한다.

시스템의 데이터 흐름은 다음과 같다. 카메라는 모든 프레임을 로컬로 제공하지만 외부로 보내지는 것은 안정 장면 변화가 확정된 사건의 증거뿐이다. 전체 장면 영상은 추론 요청 동안 메모리에 유지되며, 영구 증거는 후보의 물품 crop과 물품이 놓이기 전의 빈 배경 crop이다. 실행 중 개인정보 보호 모드를 적용하면 미리보기를 가리고 이후 capture 분석을 중단한다. 다만 전환 전에 callback 또는 VLM queue에 들어간 작업은 계속될 수 있다. 현재 구현은 프로세스 재시작 시 데이터베이스에 저장된 privacy 설정을 VisionMonitor에 자동 재적용하지 않으므로 배포 전에 부팅 동기화 보완이 필요하다.

## 3-3. 사건별 처리 정책

**표 2. 사건별 로컬 및 외부 처리 / Table 2. Local and remote processing by event type**

| 로컬 사건·내부 결과 | 의미 | 외부 VLM | DB 처리 |
|---|---|---:|---|
| added | 기존 활성 물품과 대응되지 않는 새 변화 | 호출 | 임시 물품을 먼저 생성한 뒤 의미 정보 갱신 |
| moved | 기존 물품이 다른 위치에서 재식별됨 | 호출하지 않음 | 동일 ID의 bbox·참조 영상 갱신 |
| removed | 기존 위치가 저장된 빈 배경과 명확히 일치 | 호출하지 않음 | 기존 ID를 운영상 recovered로 전환 |
| verify_removed | 제거인지 화면·외형 변화인지 모호함 | 호출 | 설정된 최소 신뢰도 이상의 제거 판단일 때만 전환 |
| 내부 억제 결과(진단 이벤트) | 화면 대부분이 동시에 변함 | 호출하지 않음 | ChangeEvent나 물품 행을 만들지 않고 기준 재설정 |

valuable, general, food의 기본 보관 기한은 각각 90일, 60일, 1일이다. 이는 법정 보관 기간이 아니라 현재 프로젝트의 운영 정책이며 관리자가 개별 물품의 기한을 수정할 수 있다. 영상에서 사라진 물품을 자동으로 recovered로 바꾸는 것 역시 시스템의 운영 상태 전환일 뿐, 실제 소유자에게 인계되었다는 물리적 사실을 증명하지 않는다.

# 4. 제안 방법

## 4-1. 안정 장면 상태기계

카메라 연결 직후 자동 노출과 초점 변화가 기준 장면에 포함되지 않도록 보정 준비 구간을 거친다. 이후 상태기계는 calibrating, monitoring, settling, stabilizing, analyzing의 다섯 주요 상태로 동작한다. monitoring에서 움직임을 감지하면 settling으로 전이하고, 마지막 움직임 이후 설정된 대기시간이 지난 뒤 stabilizing에서 연속 무동작 시간을 확인한다. 장면이 지정 시간 동안 안정된 경우에만 기준 영상과 현재 영상을 분석한다. 분석이 끝나면 현재 안정 영상을 새 기준으로 갱신하고 monitoring으로 돌아간다.

[[FIGURE_2_STATE_MACHINE]]

**그림 2. 안정 장면 사건 검출 상태 전이 / Fig. 2. State transitions for stable-scene event detection**

편집 지시: calibrating→monitoring↔settling→stabilizing→analyzing→monitoring 상태 전이도를 삽입한다.

인접 프레임만 검사하면 매우 천천히 놓이는 물품은 한 프레임의 움직임 임계값을 넘지 못할 수 있다. 이를 보완하기 위해 기준 장면과의 누적 변화도 낮은 빈도로 검사한다. 누적 변화가 충분하면 일반 움직임과 동일하게 settling과 stabilizing 절차로 진입한다. 이 설계는 행동 중 손과 사람을 물품으로 분석하는 것을 피하고, 분석 입력을 행동 전후의 안정 장면으로 제한한다.

## 4-2. 기하 정합

기준 영상 \(B\)와 현재 영상 \(I_t\)에서 Gaussian blur를 적용한 회색조 영상을 구한다. 기준 영상의 Shi–Tomasi 코너를 Lucas–Kanade 피라미드 광류로 현재 영상까지 추적한 뒤 다시 기준 영상으로 역추적한다. 순방향·역방향 오차가 허용 범위 안인 대응점만 남긴다. 대응점이 화면의 가로·세로에 충분히 퍼지고 3×3 격자의 여러 영역을 차지할 때 RANSAC 기반 부분 affine 변환을 추정한다.

\[
F^{*}=\arg\max_F \sum_i \mathbf{1}\!\left(\lVert p'_i-Fp_i\rVert_2\leq\tau\right),\qquad
T^{*}=(F^{*})^{-1},\qquad
\hat I_t=W(I_t,T^{*})
\tag{1}
\]

여기서 \(p_i\)와 \(p'_i\)는 각각 기준 및 현재 영상의 대응점이고, \(\tau\)는 RANSAC 재투영 inlier 임계값이다. \(F^{*}\)는 consensus가 최대인 기준→현재 부분 affine 변환, \(T^{*}\)는 코드에서 warping에 사용하는 그 역변환이다. \(W\)는 현재 영상을 기준 좌표계로 warping하는 연산이다. 평행이동, 회전과 크기 변화가 설정 상한을 넘는 변환은 장면 전체의 카메라 이동으로 간주하지 않고 거부한다. 부분 affine 추정에 실패하면 같은 순·역방향 추적의 강건한 중앙 평행이동을 시도한다. 이 경로도 실패하고 두 영상의 밝기 분산과 최대 이동량 조건을 만족할 때만 phase correlation을 제한적 fallback으로 사용한다. 텍스처가 거의 없는 면에서는 이 조건을 만족하지 않아 정합을 적용하지 않을 수 있다. warping으로 생긴 무효 경계와 보간 seam은 마스크에서 제외하여 인공적인 테두리가 사건 후보가 되는 것을 막는다.

## 4-3. 조명 보정과 변화 마스크

정합된 현재 영상의 휘도 차를 \(s(x)=L_{\hat I_t}(x)-L_B(x)\)로 정의한다. 먼저 유효 화소에서 \(s(x)\)의 중앙값 \(m\)을 빼 전체 노출 이동을 보정한다. 다음으로 넓은 Gaussian 평활로 국소 조명 성분 \(\ell(x)\)을 근사한다. 국소 보정이 원래 차이를 오히려 키워 halo를 만들지 않도록 최종 휘도 차를 식 (2)처럼 제한한다.

\[
D_L(x)=\min \left(
\left|s(x)-m-\ell(x)\right|,
\left|s(x)-m\right|
\right)
\tag{2}
\]

회색조 차이만으로는 바닥과 휘도가 비슷하지만 색상이 다른 물품을 놓칠 수 있다. 따라서 Lab 색공간의 두 색차를 함께 사용하여 구조 차이 영상을 식 (3)으로 구성한다.

\[
D(x)=\max\left(D_L(x),\,|\Delta a(x)|,\,|\Delta b(x)|\right)
\tag{3}
\]

초점 호흡과 sub-pixel 진동은 기존 경계 양쪽에 띠 형태의 차이를 남긴다. 본 시스템은 두 영상의 Sobel 경계가 작은 이웃 안에서 함께 존재하는 화소를 “지속 경계”로 표시하고 후보의 핵심 마스크에서 억제한다. 새 물품의 내부나 이전에 경계가 없었던 윤곽은 양쪽 영상에 공통으로 존재하지 않으므로 그대로 남는다.

\(D(x)\)를 임계값으로 이진화한 뒤 3×3 열림, 9×9 닫힘과 5×5 팽창을 차례로 적용한다. 연결 성분은 면적과 밀도에 따라 표준형, 작은 조밀형, 긴 세장형 후보로 나누어 필터링하고 가까운 상자를 병합한다. 전역 보정 차이에서 낮은 임계값으로 얻은 support mask는 이미 검출된 상자를 확장하는 데만 사용한다. 이와 별도로 국소 보정이 저대비 물품 내부를 지운 경우에는 최소 면적·밀도·날카로운 경계 조건을 만족하고 조명 변화 전용 검사를 통과한 fallback 성분이 독립 후보가 될 수 있다. 화면 전체에서 변화 마스크가 차지하는 비율이 상한을 넘으면 조명 전환 또는 카메라 충격 같은 전역 변화로 억제한다. 화면 테두리의 길고 얇은 변화, 부드러운 밝기 변화와 색차가 작은 그림자 후보도 별도 규칙으로 거부한다.

[[FIGURE_3_PIPELINE_STAGES]]

**그림 3. 로컬 변화 검출의 중간 결과 / Fig. 3. Intermediate results of local change detection**

편집 지시: 같은 사건의 원본 전후, 정합 후, 보정 차이, 이진 마스크와 최종 bbox를 삽입한다.

## 4-4. 활성 물품 대응과 사건 판정

데이터베이스에서 현재 stored 또는 due 상태인 물품을 활성 물품으로 읽고, 등록 당시 저장한 물품 경계상자, 물품 crop 및 물품 배치 전의 빈 배경 crop을 로컬 검출기에 제공한다. 먼저 변화 후보와 활성 상자의 겹침으로 기존 위치 후보를 대응한다. 기존 상자와 떨어진 새 후보의 relocation 검사에서는 중심 거리와 크기 조건을 추가로 사용한다.

기존 위치의 변화 후 영상이 저장된 빈 배경 crop과 충분히 유사하고 등록 물품과의 유사도가 낮아지면 removed로 판정한다. 반대로 휴대전화 화면 점등처럼 경계상자 내부의 외형만 바뀌었거나 제거 근거가 경계값에 가까우면 자동 회수하지 않고 verify_removed로 분기한다.

기존 상자와 새 후보 상자가 함께 나타나는 경우에는 같은 물품의 이동 가능성을 검사한다. 빠른 경로는 등록 물품 템플릿과 후보 영역의 상관도, Lab 색상과 물체 영역 유사도를 결합한다. 고정 크기 템플릿이 배경 또는 크기 변화 때문에 불리한 경우에는 물품 전경에서 ORB 특징[26]을 추출하고, 양방향 비율 검사와 RANSAC 변환으로 재검증한다. 대응이 성공하면 새 물품 레코드를 만들지 않고 기존 item_id의 경계상자와 참조 crop을 갱신하며 moved 활동을 기록한다.

어떤 활성 물품과도 대응되지 않는 후보는 added로 발행한다. 한 분석 구간에서 전역 변화가 감지되면 국소 사건보다 전역 억제를 우선하고 현재 안정 장면으로 기준을 다시 설정한다.

## 4-5. 선택적 멀티모달 추론과 증거 구성

added 사건이 발생하면 후보 영역의 전·후 고해상도 crop과, 후보 상자가 표시된 전·후 전체 장면을 준비한다. 전체 장면은 변화 방향과 주변 문맥을 판단하는 저해상도 입력으로, crop은 물품의 종류, 색상과 재질을 식별하는 고해상도 입력으로 사용한다. 최대 입력 수는 네 장으로 고정한다.

모델에는 action, name, description, category, estimated_value_krw와 confidence를 JSON 형식으로 응답하도록 요청하고, 반환 문자열을 파싱한다. 형식 오류는 실패로 처리한다. action은 added, removed, uncertain 중 하나이고 category는 valuable, general, food 중 하나이다. 전체 장면과 crop의 결론이 충돌하거나 새 물품이 분명하지 않으면 uncertain을 반환하도록 요청한다. added의 낮은 신뢰도 결과는 신규 레코드를 확인 필요 상태로 남긴다.

verify_removed 사건에서도 같은 전후 증거 구조를 사용하지만, removed 응답이 설정된 최소 신뢰도 이상일 때만 기존 물품을 recovered로 전환한다. uncertain 또는 낮은 신뢰도이면 물품 상태와 추적을 유지하고 활동 로그를 남긴다. moved와 명확한 removed는 로컬 참조 정보로 판단되므로 원격 요청을 만들지 않는다. 이에 따라 네트워크 전송 단위는 연속 프레임이 아니라 로컬에서 선별된 사건이다.

## 4-6. 임시 저장과 오래된 응답 방지

change callback worker가 정상 접수한 신규 added 사건은 원격 요청 전에 물품 crop, 빈 배경 crop과 provider=pending인 임시 데이터베이스 행으로 저장된다. 이후 bounded worker에서 비동기 분류를 수행한다. API 키 부재, timeout, 응답 형식 오류, 원격 작업 대기열 포화 또는 낮은 신뢰도에서도 이미 생성된 임시 물품은 삭제하지 않고 확인 필요 상태로 보존한다. 반대로 멀티모달 모델이 충분히 높은 신뢰도로 “제거 방향”을 판정한 경우에만 잘못 생성된 임시 등록을 취소할 수 있다. 단, change callback queue가 임시 행 생성 전에 포화되면 사건 자체가 drop될 수 있으므로 이를 별도 장애 지표로 측정한다.

분류가 진행되는 동안 관리자가 정보를 수정하거나 물품이 이동·회수될 수 있다. added 분류는 임시 행의 provider가 여전히 pending인지 확인하여 관리자 수정 결과를 유지하고, 비확정 분기에서는 현재 상태와 bbox 변화를 추가로 확인한다. verify_removed는 요청 전후의 bbox, 참조 파일 경로와 갱신 시각으로 구성된 추적 signature가 모두 같은 경우에만 결과를 적용한다. 따라서 완전한 signature 재검사는 제거 검증 경로에 한정된다. 회수·폐기·복원과 활동 기록은 SQLite의 같은 트랜잭션에서 처리한다.

[[FIGURE_4_SEQUENCE]]

**그림 4. 임시 저장과 선택적 추론 처리 순서 / Fig. 4. Provisional persistence and selective inference sequence**

편집 지시: local added→provisional DB→VLM→성공/불확실/실패 분기와 moved·removed 로컬 경로를 삽입한다.

## 4-7. 전체 알고리즘

**알고리즘 1. 안정 장면 기반 사건 처리 / Algorithm 1. Event processing over stable scenes**

1. 카메라 준비 이후 안정 장면을 기준 영상 \(B\)로 설정한다.
2. 인접 프레임과 기준 장면의 차이로 움직임 또는 누적 변화를 감시한다.
3. 마지막 움직임 이후 settle 시간과 연속 stable 시간을 만족할 때 현재 영상 \(I_t\)를 확정한다.
4. 특징 기반 부분 affine 또는 제한된 평행이동으로 \(I_t\)를 \(B\)에 정합한다.
5. 전역·국소 조명, Lab 색차 및 지속 경계를 고려하여 변화 마스크와 후보 상자를 생성한다.
6. 변화 비율이 전역 상한을 넘으면 물품 사건을 억제한다.
7. 전역 변화가 아니면 후보를 활성 물품의 bbox, 물품 crop 및 빈 배경 crop과 대응한다.
8. 대응 결과에 따라 moved, removed, verify_removed 또는 added를 생성한다.
9. 로컬 분석 직후 결과 종류와 관계없이 \(B\leftarrow I_t\)로 갱신하고 monitoring으로 돌아간 뒤 사건 callback을 처리한다.
10. moved와 removed는 기존 ID에 로컬 반영한다.
11. added는 임시 레코드를 저장한 뒤 멀티모달 추론을 수행한다. verify_removed는 기존 물품의 추적 signature를 메모리에 보관하고 같은 최대 4장 증거로 추론한다.
12. added 응답은 임시 행이 pending일 때 적용하고, verify_removed 응답은 현재 signature가 요청 시점과 일치할 때만 신뢰도 정책에 따라 반영한다.

# 5. 구현 및 실험 설계

## 5-1. 구현 환경

Re:Found의 엣지 장치는 Raspberry Pi 4 Model B 2GB이며 CSI 카메라와 Picamera2/OpenCV를 사용한다. 애플리케이션은 Python 기반 FastAPI 단일 backend, SQLite WAL, vanilla HTML/CSS/JavaScript 관리자 화면으로 구성된다. 운영 서비스는 systemd로 시작하며 로컬 네트워크, Tailscale 또는 인터넷이 없는 경우 장치 hotspot에서 접근할 수 있다.

**표 3. Raspberry Pi 기본 영상 설정 / Table 3. Default vision settings for Raspberry Pi**

| 항목 | 설정값 |
|---|---:|
| 카메라 입력 해상도 | 1280×720 |
| 카메라 FPS | 10 |
| 로컬 감시 목표 FPS | 7 |
| 누적 변화 검사 FPS | 2 |
| 웹 미리보기 FPS | 5 |
| 정합 분석 폭 | 360 pixel |
| 후보 crop JPEG 품질 | 88 |
| 전체 장면 JPEG 품질 | 72 |
| 변화 threshold | 24 |
| 최소 변화 면적 | 1,800 pixel |
| 움직임 종료 대기 | 3.0 s |
| 추가 안정 확인 | 1.2 s |
| 외부 분류 worker | 1 |
| 동시 실행·대기 slot 상한 | 4 |

표 3은 소스 코드의 Raspberry Pi profile 기본값이다. 실험에서 설정을 변경한 경우 실제 실행 configuration과 detector 소스 hash를 결과와 함께 보관하고, 논문 표에는 실제 사용값을 보고한다. 실험 장치의 OS, 카메라 모듈, 렌즈, 냉각과 전원은 표 4에 별도로 기록한다.

**표 4. 실제 평가 장비 / Table 4. Hardware and software used in evaluation**

| 항목 | 실제 값 |
|---|---|
| 보드·메모리 | Raspberry Pi 4 Model B, 2 GB |
| 운영체제·커널 | [[EQUIP_OS_KERNEL]] |
| 카메라·렌즈 | [[EQUIP_CAMERA_LENS]] |
| 카메라 고정 거리·각도 | [[EQUIP_CAMERA_GEOMETRY]] |
| 저장장치 | [[EQUIP_STORAGE]] |
| 냉각·케이스 | [[EQUIP_COOLING]] |
| 전원·전력 계측점 | [[EQUIP_POWER_AND_METER]] |
| OpenCV/Python 버전 | [[EQUIP_OPENCV_PYTHON]] |
| VLM provider·model·버전/일자 | [[VLM_PROVIDER_MODEL_DATE]] |
| 네트워크 조건 | [[NETWORK_CONDITION]] |

## 5-2. 평가 데이터와 라벨링

실험 단위는 한 번의 행동과 그 후 안정화를 포함한 episode이다. 정답 사건은 added, removed, moved, none으로 구성하고, 내부 중간 상태인 verify_removed는 정답 종류에서 제외한다. 양성 사건에는 \(x,y,w,h\) 형식의 경계상자를 표시한다. moved의 정답 bbox는 이동 후 새 위치로 정의하고, 이동 전 위치와 item_id는 active_bbox와 active_item_id에 별도 기록한다. `action_end_at`은 물품 또는 이를 조작하는 손의 마지막 물리적 접촉이 끝나고 물품이 최종 상태에 머물기 시작한 첫 frame의 시각으로 라벨링한다. 같은 episode를 모든 ablation profile에 입력하여 대응 비교한다.

평가 자료는 목적에 따라 네 집합으로 분리한다. \(D_{pair}\)는 안정 전후 영상쌍으로 detector core와 표 8의 단계적 ablation에만 사용한다. \(D_{stream}\)은 연속 replay 또는 실시간 camera episode로 상태기계, ID, 표 7, false events/hour와 종단간 지연을 평가한다. \(D_{vlm}\)은 같은 사건 증거를 고정한 V1–V4 비교용이고, \(D_{fault}\)는 network 차단, timeout, malformed JSON, queue 포화와 오래된 응답을 통제하여 주입하는 장애 자료이다.

개발 표본과 최종 평가 표본을 분리한다. 평가 결과를 본 뒤 임계값을 조정한 표본은 최종 평가에 재사용하지 않고 개발 세트로 돌린다. 최종 평가 설정은 사전에 고정하고 실패 표본도 제외하지 않는다. 두 라벨러가 무작위 [[DOUBLE_LABEL_RATIO]]%를 독립 판정하고, 사건 종류의 Cohen’s \(\kappa\) [[LABEL_KAPPA]]와 bbox IoU [[LABEL_BBOX_IOU]]를 보고한 뒤 불일치를 합의한다.

**표 5. 평가 데이터 구성 / Table 5. Composition of the evaluation dataset**

| 사건 | 조건 | 개발 세트 | 최종 평가 세트 |
|---|---|---:|---:|
| added | 물품 [[OBJECT_TYPE_COUNT]]종, 거리·조명 교차 | [[N_DEV_ADDED]] | [[N_TEST_ADDED]] |
| removed | 동일 물품과 방해 조건 | [[N_DEV_REMOVED]] | [[N_TEST_REMOVED]] |
| moved | 이동 거리·크기·부분 가림 포함 | [[N_DEV_MOVED]] | [[N_TEST_MOVED]] |
| none | 정상·노출·그림자·jitter·초점·가림 | [[N_DEV_NONE]] | [[N_TEST_NONE]] |
| 합계 | 장소 [[SITE_COUNT]]곳, 촬영일 [[CAPTURE_DAY_COUNT]]일 | [[N_DEV_TOTAL]] | [[N_EVAL_EPISODES]] |

표 5의 최종 평가는 \(D_{stream}\)의 episode 수를 나타낸다. \(D_{pair}\)의 최종 공통 영상쌍은 [[N_PAIR_EVAL]]개이다. \(D_{vlm}\)은 exact action을 채점할 decisive 표본 [[N_VLM_ACTION]]개 중 GT-added [[N_VLM_GT_ADDED]]개와 GT-removed [[N_VLM_GT_REMOVED]]개, 그리고 안전한 상태 유지 결정을 따로 평가할 non-removal/retain 표본 [[N_VLM_RETAIN]]개로 구성하며 각 증거 구성을 사례당 [[VLM_REPEATS_PER_CASE]]회 반복한다. 연속 none 감시는 총 [[NONE_MONITORING_HOURS]]시간 수행한다. 워밍업, 의도적 카메라 중단과 연결 끊김은 유효 감시시간에서 제외하고 제외 구간을 원장에 기록한다. 안정 이미지 쌍의 source segment 길이는 촬영 출처 정보일 뿐, 연속 감시의 false events/hour 분모로 사용하지 않는다.

## 5-3. 비교 구성과 ablation

로컬 방해요인 방어 로직의 단계적 변화를 확인하기 위해 \(D_{pair}\)의 동일 안정 이미지 쌍에 표 6의 누적 profile을 적용한다.

**표 6. 로컬 방해요인 방어 ablation / Table 6. Ablation profiles for nuisance defenses**

| profile | 기하 정합 | 전역 노출 보정 | 지속 경계 억제 | 국소 조명 보정 |
|---|---:|---:|---:|---:|
| plain | × | × | × | × |
| aligned | ○ | × | × | × |
| aligned_global | ○ | ○ | × | × |
| aligned_global_jitter | ○ | ○ | ○ | × |
| full | ○ | ○ | ○ | ○ |

다섯 profile은 Lab 색차, morphology, contour, 그림자·전역 변화 거부와 활성 물품 사건 로직을 공유한다. 따라서 plain은 “순수 회색조 절대차”가 아니라 방해요인 방어 네 요소를 끈 공통 코어이다. 또한 앞 단계가 유지된 상태에서 다음 요소를 더하는 누적 구성이라 각 모듈의 독립적 인과효과를 뜻하지 않는다. 차이는 고정된 순서에서의 조건부 변화로 해석하고, 독립 효과가 필요하면 full에서 한 요소씩 제거하는 leave-one-out을 추가한다.

핵심 baseline과 제안 방법은 모두 \(D_{stream}\)의 같은 replay 구간에서 비교한다.

- B0: 순수 회색조 절대차와 면적 threshold [[IMPLEMENT_AND_RUN_PURE_ABSDIFF]]
- B1: frame-level 코어만 사용하고 settle/stable 상태기계를 사용하지 않은 replay [[IMPLEMENT_AND_RUN_NO_STATE_MACHINE]]
- B2: OpenCV MOG2와 동일한 개발 세트 조정·사건 시간창·후처리 조건 [[IMPLEMENT_AND_RUN_MOG2]]
- P1: 본 연구 전체 로컬 pipeline
- V1: 변화 후 crop 1장
- V2: 후보 crop 전·후 2장
- V3: 전체 장면 전·후 2장
- V4: 전체 장면 전·후와 후보 crop 전·후 4장

B0–B2는 입력 FPS, 워밍업 [[BASELINE_WARMUP_SECONDS]]초, 후보 병합 시간창과 활성 물품 대응을 동일하게 하고 foreground 생성기와 상태기계 사용 여부만 다르게 한다. foreground 후보를 added/moved/removed로 변환하는 공통 adapter는 [[BASELINE_EVENT_ADAPTER_PROTOCOL]], B0·B1의 참조 영상 갱신 규칙은 [[B0_B1_REFERENCE_UPDATE_RULE]], B2의 history·varThreshold·background ratio·learning rate는 [[B2_MOG2_PARAMETERS]]로 개발 세트에서 고정한다. 이 항목을 확정하기 전에는 세 사건 종류의 Macro-F1을 baseline 간 비교하지 않는다.

VLM 비교에서는 \(D_{vlm}\)의 같은 사건, 같은 단일 provider와 모델 ID, 동일 실행 기간, 동일한 prompt 공통 부분 및 무작위화한 호출 순서를 사용하며 auto fallback을 끈다. exact action 정확도는 GT-added와 GT-removed의 decisive 표본에서 uncertain을 오답으로 채점한다. 이와 별도로 added 경로의 register/hold 결정과 verify_removed 경로의 recover/retain 결정을 운영 이진 지표로 평가하여, non-removal 사례에서 안전한 uncertain을 의미 오분류와 구분한다. 물품명·category 정확도는 GT-added에만 계산하고 uncertain 비율, non-abstained 정확도, 요청 byte, token/비용과 지연을 기록한다. 원격 모델은 시간에 따라 바뀔 수 있으므로 provider, model ID, 실행 날짜, 반복 횟수와 prompt hash를 함께 저장한다. 현재 애플리케이션은 이 usage와 timestamp를 보존하지 않으므로 실험 전에 별도 VLM 원장을 추가한다.

## 5-4. 평가 지표와 통계

정답 상자 \(B_g\)와 예측 상자 \(B_p\)의 IoU는 식 (4)로 정의한다.

\[
\operatorname{IoU}(B_g,B_p)=
\frac{|B_g\cap B_p|}{|B_g\cup B_p|}
\tag{4}
\]

사건 종류가 같고 IoU가 0.30 이상이며 사전에 정한 시간창 안에 있는 정답과 예측을 episode별 일대일 최적으로 매칭한다. 0.30은 작은 물품과 보정 후 확장된 후보를 허용하는 사전 protocol 값이며, IoU 0.50에서도 민감도 분석을 함께 제시한다. 매칭 수를 먼저 최대화하고, 동률이면 더 이른 자격 예측과 높은 IoU를 순서대로 사용한다. 종류별 precision, recall과 F1은 식 (5)로 계산한다.

\[
P=\frac{TP}{TP+FP},\qquad
R=\frac{TP}{TP+FN},\qquad
F1=\frac{2TP}{2TP+FP+FN}
\tag{5}
\]

added, removed, moved의 support와 함께 micro 및 macro 값을 보고한다. 표 7의 “로컬 확정 사건” 평가에서 verify_removed는 제거 정답으로 직접 맞추지 않고 보류로 처리하므로, 최종 removed가 없는 해당 episode는 로컬 removed FN에 포함된다. 이와 별도로 removed 또는 verify_removed가 제거 정답 위치를 찾은 비율인 제거 후보 recall과, 그중 verify_removed로 보낸 referral 비율을 보고한다. VLM 이후의 확정 removed는 final stage에서 다시 채점한다. none episode의 오작동률은 하나 이상의 확정 사건을 낸 none episode의 비율이고, verify_removed/VLM referral 발생률은 비용 지표로 별도 집계한다. 연속 감시 오탐률은 식 (6)과 같다.

\[
\text{False events/hour}=
\frac{N_{\mathrm{FP,none}}}{T_{\mathrm{eligible,h}}}
\tag{6}
\]

안정 이미지 쌍은 유효 wall-clock 감시시간을 제공하지 않으므로 해당 자료에서 false events/hour를 계산하지 않는다. ID 보존율과 ID 할당 오류율은 정답 및 예측 item_id가 모두 존재하는 matched moved TP에서만 계산하고, scorable N과 coverage를 함께 제시한다. 운영 중복 행 생성률은 이 조건부 지표와 분리하여, 전체 GT-moved episode 중 added 오분류 등을 통해 기존 ID 외의 새 DB 행이 생성된 비율로 정의한다. 예측 ID를 생성하지 않는 안정 이미지 쌍 실험으로 어느 ID 지표도 주장하지 않는다.

누적 지연은 action_end→local event, action_end→provisional DB와 action_end→final commit으로 정의하고, AI round trip은 ai_request_at→ai_response_at으로 별도 계산한다. 지연 분포는 성공적으로 매칭된 TP에 조건부이므로 각 분포에 유효 N/전체 N, recall과 timestamp 결측률을 함께 제시한다.

같은 촬영 구간의 반복 episode가 독립이 아닐 수 있으므로 recording session을 주 cluster 단위로 사전 고정한 10,000회 bootstrap 95% 신뢰구간을 precision, recall, F1, Macro-F1, IoU, 지연과 profile 차이에 사용한다. 동일 물품은 development와 final evaluation에 걸치지 않게 group 분할하고, physical item을 cluster로 둔 결과는 민감도 분석으로만 제시한다. bootstrap seed는 [[BOOTSTRAP_SEED]]로 고정한다. 단순 비율의 Wilson 구간을 보조로 제시하고, false events/hour에는 Poisson exact 구간과 run-block bootstrap을 사용한다. McNemar 검정은 F1 자체가 아니라 “해당 episode의 모든 정답 사건을 여분 확정 사건 없이 맞혔는가”라는 paired 이진 endpoint에만 적용하고 Holm으로 다중비교를 보정한다. V1–V4도 같은 사건의 paired 비교와 session-cluster bootstrap을 사용하며 유의수준은 .05로 정한다.

선택 정책, 조건부 VLM과 종단간 업무 성능은 서로 다른 분모로 보고한다. added gate recall의 분모는 모든 GT-added이고, removal gate recall의 분모는 결과를 보지 않은 두 라벨러가 사전 기준으로 지정한 [[N_GT_AMBIGUOUS_REMOVAL]]개 모호 제거 episode이다. 각각에서 logical inference job이 생성된 비율과 provider HTTP attempt 수를 사용한다. VLM 조건부 성능은 \(D_{vlm}\)의 실제 입력 대상 안에서 평가하고, name과 category는 GT-added에만 적용한다. decisive GT-added/removed의 exact action에서 uncertain은 오답으로 처리하되 coverage와 응답한 표본만의 selective accuracy를 함께 보고한다. 종단간 업무 성공은 \(D_{stream}\)에서 로컬 누락까지 포함해 added는 올바른 등록, moved는 기존 ID 갱신, removed는 최종 운영 상태 전환까지 완료한 episode 비율로 정의하고 사건 종류별 및 macro 값을 함께 보고한다.

선택 호출의 전송량 비교에서 no-gating 기준선은 analyzing에 도달한 모든 eligible episode의 전후 전체 장면을 제안 방법과 같은 해상도와 JPEG 품질 72로 전송한다. 후보가 없는 none episode에 가상 crop을 만들지 않는다. 전송 byte는 HTTP/TLS header를 제외하고 base64와 JSON을 포함한 직렬화 요청 payload 크기로 정의하며, JPEG 원본 byte 합도 보조 원장에 남긴다. 선택 정책의 실제 1–4장 payload와 이 기준선의 누적 byte 및 요청 수를 같은 replay 구간에서 비교하되, 증거 구성이 다르므로 이를 VLM 정확도의 직접 비교로 해석하지 않는다.

## 5-5. 장치 자원과 운영 안정성

Raspberry Pi에서 서비스와 동시에 1초 간격으로 주 프로세스 CPU, device-normalized CPU, RSS, system CPU, 가용 메모리, load, 저장공간과 thermal-zone 온도를 기록한다. 첫 CPU 표본은 누적값 차분이 없어 제외할 수 있다. 전력은 소프트웨어로 추정하지 않고 외부 AC 또는 USB 전력계가 있을 때만 측정점, 주변장치 포함 범위, 계측기 정확도와 sampling rate를 함께 보고한다.

[[LONG_RUN_DURATION_HOURS]]시간 연속 실행에서 카메라 disconnect, reconnect 시간, 원격 요청 실패, provisional 보존, DB 오류와 서비스 재시작을 기록한다. capture read 실패, monitor scheduler skip과 callback queue drop은 서로 다른 지표로 정의한다. 현재 코드는 누적 frame/drop counter와 영속 원장을 제공하지 않으므로 실험 전에 계측을 추가해야 하며, queue 포화 시 물품 change와 진단 callback도 구분한다. \(D_{fault}\)에서는 실패 유형별 주입 횟수와 보존·복구 결과를 보고한다. 소스 코드의 자동화 test [[REGRESSION_TEST_COUNT]]개 통과 여부는 구현 회귀 검증으로만 보고하며 현장 인식 정확도의 근거로 사용하지 않는다.

# 6. 결과 및 논의

> 이 절의 표와 문장은 실험 결과 입력용 완성 골격이다. 이중 대괄호 항목을 실제 원장과 집계 결과로 교체하기 전에는 투고하지 않는다.

## 6-1. 사건 검출 성능

**표 7. \(D_{stream}\)의 로컬 확정 사건 및 baseline 성능 / Table 7. Decisive local-event and baseline performance on \(D_{stream}\)**

(a) 제안 방법의 사건 종류별 결과

| 사건 | Support | Precision (95% CI) | Recall (95% CI) | F1 (cluster 95% CI) | IoU p50 (cluster 95% CI) |
|---|---:|---:|---:|---:|---:|
| added | [[SUPPORT_ADDED]] | [[P_ADDED_CI]] | [[R_ADDED_CI]] | [[F1_ADDED]] | [[IOU_ADDED_P50]] |
| removed | [[SUPPORT_REMOVED]] | [[P_REMOVED_CI]] | [[R_REMOVED_CI]] | [[F1_REMOVED]] | [[IOU_REMOVED_P50]] |
| moved | [[SUPPORT_MOVED]] | [[P_MOVED_CI]] | [[R_MOVED_CI]] | [[F1_MOVED]] | [[IOU_MOVED_P50]] |
| micro | [[SUPPORT_TOTAL_POSITIVE]] | [[P_MICRO_CI]] | [[R_MICRO_CI]] | [[F1_MICRO]] | [[IOU_ALL_P50]] |
| macro | — | [[P_MACRO]] | [[R_MACRO]] | [[LOCAL_MACRO_F1]] ([[LOCAL_MACRO_F1_CI]]) | — |

(b) 공통 replay 구간의 전체 구성 비교

| 구성 | Macro-F1 | none 오작동률 | FP/hour (Poisson 95% CI) | local p95 (ms) |
|---|---:|---:|---:|---:|
| B0: pure absdiff | [[B0_MACRO_F1]] | [[B0_NONE_RATE]] | [[B0_FP_HOUR]] | [[B0_LOCAL_P95]] |
| B1: no state machine | [[B1_MACRO_F1]] | [[B1_NONE_RATE]] | [[B1_FP_HOUR]] | [[B1_LOCAL_P95]] |
| B2: MOG2 | [[B2_MACRO_F1]] | [[B2_NONE_RATE]] | [[B2_FP_HOUR]] | [[B2_LOCAL_P95]] |
| P1: Re:Found full | [[LOCAL_MACRO_F1]] | [[NONE_EPISODE_TRIGGER_RATE_CI]] | [[FALSE_EVENTS_PER_HOUR]] | [[LOCAL_LATENCY_P95_MS]] |

[[RESULT_BASELINE_INTERPRETATION]] IoU 0.50 민감도 분석에서 제안 방법의 Macro-F1과 95% CI는 [[IOU50_MACRO_F1_CI]]였다. 제안 방법에서 사건 종류별 가장 높은 F1은 [[BEST_EVENT_KIND]]의 [[BEST_EVENT_F1]], 가장 낮은 값은 [[WORST_EVENT_KIND]]의 [[WORST_EVENT_F1]]였다. [[RESULT_EVENT_INTERPRETATION]] removed와 verify_removed를 모두 후보로 인정한 제거 후보 recall은 [[REMOVAL_CANDIDATE_RECALL_CI]], 후보 중 verify_removed referral 비율은 [[REMOVAL_VERIFY_REFERRAL_RATE_CI]]였다.

moved 사건의 ID 평가는 전체 중 [[MOVED_ID_SCORABLE_N]]개([[MOVED_ID_COVERAGE]])에서 가능했다. scorable matched TP의 기존 ID 보존율은 [[MOVED_ID_RETENTION_CI]], 다른 ID 할당률은 [[MOVED_ID_ASSIGNMENT_ERROR_CI]]였다. 이와 별도로 전체 GT-moved episode에서 추가 DB 행이 만들어진 운영 중복 행 생성률은 [[MOVED_DUPLICATE_ID_RATE_CI]]였다.

none episode의 확정 사건 오작동률은 [[NONE_EPISODE_TRIGGER_RATE_CI]], verify_removed referral 비율은 [[NONE_VERIFY_REFERRAL_RATE_CI]]였다. [[NONE_MONITORING_HOURS]]시간의 연속 무사건 감시에서는 [[NONE_FALSE_EVENT_COUNT]]건, 즉 [[FALSE_EVENTS_PER_HOUR]]건/시간의 확정 오탐이 발생하였다. 이 비율의 Poisson exact 95% CI는 [[FALSE_EVENTS_PER_HOUR_POISSON_CI]], run-block bootstrap 95% CI는 [[FALSE_EVENTS_PER_HOUR_BLOCK_CI]]였다. 가장 빈번한 원인은 [[MOST_COMMON_FALSE_TRIGGER]]였다.

## 6-2. 방해요인 방어 ablation

**표 8. \(D_{pair}\)의 단계적 방해요인 방어 구성(\(N\)=[[N_PAIR_EVAL]]) / Table 8. Incremental nuisance-defense configurations on \(D_{pair}\) (\(N\)=[[N_PAIR_EVAL]])**

| profile | Macro-F1 | none 오작동률 | core p50/p95 (ms) | episode-correct McNemar p |
|---|---:|---:|---:|---:|
| plain | [[ABL_PLAIN_F1]] | [[ABL_PLAIN_NONE_RATE]] | [[ABL_PLAIN_LATENCY]] | [[ABL_PLAIN_P_ADJ]] |
| aligned | [[ABL_ALIGNED_F1]] | [[ABL_ALIGNED_NONE_RATE]] | [[ABL_ALIGNED_LATENCY]] | [[ABL_ALIGNED_P_ADJ]] |
| aligned_global | [[ABL_GLOBAL_F1]] | [[ABL_GLOBAL_NONE_RATE]] | [[ABL_GLOBAL_LATENCY]] | [[ABL_GLOBAL_P_ADJ]] |
| aligned_global_jitter | [[ABL_JITTER_F1]] | [[ABL_JITTER_NONE_RATE]] | [[ABL_JITTER_LATENCY]] | [[ABL_JITTER_P_ADJ]] |
| full | [[ABL_FULL_F1]] | [[ABL_FULL_NONE_RATE]] | [[ABL_FULL_LATENCY]] | 기준 |

plain에서 full로 갈 때 Macro-F1은 [[ABL_F1_DELTA]] 변했고 none 오작동률은 [[ABL_NONE_DELTA]] 변했다. [[RESULT_ABLATION_INTERPRETATION]] 단, 이 결과는 공통 contour 및 사건 로직 안에서 고정 순서의 누적 구성을 비교한 것이며 개별 요소의 독립 효과나 순수 차영상 전체 baseline과의 비교가 아니다.

**표 9. 방해요인별 full profile 오작동 / Table 9. Errors of the full profile by nuisance type**

| 방해요인 | Challenge episode | FP | FN | episode 오작동률 |
|---|---:|---:|---:|---:|
| 전역 노출 변화 | [[NUIS_EXPOSURE_N]] | [[NUIS_EXPOSURE_FP]] | [[NUIS_EXPOSURE_FN]] | [[NUIS_EXPOSURE_RATE]] |
| 국소 조명·그림자 | [[NUIS_SHADOW_N]] | [[NUIS_SHADOW_FP]] | [[NUIS_SHADOW_FN]] | [[NUIS_SHADOW_RATE]] |
| 미세진동 | [[NUIS_JITTER_N]] | [[NUIS_JITTER_FP]] | [[NUIS_JITTER_FN]] | [[NUIS_JITTER_RATE]] |
| 초점 변화 | [[NUIS_FOCUS_N]] | [[NUIS_FOCUS_FP]] | [[NUIS_FOCUS_FN]] | [[NUIS_FOCUS_RATE]] |
| 가림·겹침 | [[NUIS_OCCLUSION_N]] | [[NUIS_OCCLUSION_FP]] | [[NUIS_OCCLUSION_FN]] | [[NUIS_OCCLUSION_RATE]] |
| 정상 none | [[NUIS_NONE_N]] | [[NUIS_NONE_FP]] | — | [[NUIS_NONE_RATE]] |

## 6-3. Raspberry Pi 처리 성능

**표 10. Raspberry Pi 종단간 성능과 자원 / Table 10. End-to-end performance and resource use on Raspberry Pi**

| 지표 | 유효 N/전체 N | 평균 | p50 | p95 | 최대 |
|---|---:|---:|---:|---:|---:|
| local event 지연 (ms) | [[N_LAT_LOCAL]] | [[LAT_LOCAL_MEAN]] | [[LOCAL_LATENCY_P50_MS]] ([[LOCAL_LATENCY_P50_CI]]) | [[LOCAL_LATENCY_P95_MS]] ([[LOCAL_LATENCY_P95_CI]]) | [[LAT_LOCAL_MAX]] |
| provisional DB 지연 (ms) | [[N_LAT_DB]] | [[LAT_DB_MEAN]] | [[LAT_DB_P50]] | [[LAT_DB_P95]] | [[LAT_DB_MAX]] |
| AI round trip (ms) | [[N_LAT_AI]] | [[LAT_AI_MEAN]] | [[LAT_AI_P50]] | [[LAT_AI_P95]] | [[LAT_AI_MAX]] |
| final commit 지연 (ms) | [[N_LAT_FINAL]] | [[LAT_FINAL_MEAN]] | [[LAT_FINAL_P50]] | [[LAT_FINAL_P95]] | [[LAT_FINAL_MAX]] |
| process CPU (%) | [[N_RESOURCE]] | [[CPU_MEAN]] | [[CPU_P50]] | [[CPU_P95]] | [[CPU_MAX]] |
| device-normalized CPU (%) | [[N_RESOURCE]] | [[CPU_NORM_MEAN]] | [[CPU_NORM_P50]] | [[CPU_NORM_P95]] | [[CPU_NORM_MAX]] |
| RSS (MiB) | [[N_RESOURCE]] | [[RSS_MEAN]] | [[RSS_P50]] | [[RSS_P95]] | [[RSS_MAX]] |
| thermal-zone (°C) | [[N_RESOURCE_TEMP]] | [[TEMP_MEAN]] | [[TEMP_P50]] | [[TEMP_P95]] | [[TEMP_MAX]] |

전체 지연 timestamp 결측률은 [[LATENCY_TIMESTAMP_MISSING_RATE]]였다. 실제 감시 처리율은 [[ACHIEVED_MONITOR_FPS]] FPS였고, capture read 실패는 [[CAPTURE_READ_FAILURE_COUNT]]건, monitor scheduler skip 비율은 [[MONITOR_SCHEDULER_SKIP_RATE]]였다. change callback과 진단 callback의 queue drop은 각각 [[CHANGE_CALLBACK_DROP_COUNT]], [[DIAGNOSTIC_CALLBACK_DROP_COUNT]]건이었다. [[RESULT_RESOURCE_INTERPRETATION]] 전력은 [[POWER_MEASUREMENT_STATUS]]이며, 계측한 경우 idle/감시/사건 분석에서 각각 [[POWER_IDLE_W]], [[POWER_MONITOR_W]], [[POWER_EVENT_W]] W였다.

안정 이미지 쌍의 core 시간은 _detect_changes 한 번의 계산만 포함하므로 표 10의 카메라 입력, 상태기계, callback, DB 및 VLM을 포함한 종단간 지연과 구분한다.

## 6-4. 선택적 멀티모달 추론

**표 11. 시각 증거 구성별 멀티모달 결과(decisive action \(N\)=[[N_VLM_ACTION]], 사례당 [[VLM_REPEATS_PER_CASE]]회) / Table 11. Multimodal results by visual evidence configuration (decisive action \(N\)=[[N_VLM_ACTION]], [[VLM_REPEATS_PER_CASE]] repetitions per case)**

| 입력 구성 | Action 정확도 전체/응답 | Category 정확도¹ | 물품 의미 정확도¹ | coverage/uncertain | p50/p95 지연 | 평균 요청 byte |
|---|---:|---:|---:|---:|---:|---:|
| V1: after crop 1장 | [[V1_ACTION_ACC]] / [[V1_ACTION_SELECTIVE_ACC]] | [[V1_CATEGORY_ACC]] | [[V1_NAME_ACC]] | [[V1_COVERAGE]] / [[V1_UNCERTAIN]] | [[V1_LATENCY]] | [[V1_BYTES]] |
| V2: crop 전·후 | [[V2_ACTION_ACC]] / [[V2_ACTION_SELECTIVE_ACC]] | [[V2_CATEGORY_ACC]] | [[V2_NAME_ACC]] | [[V2_COVERAGE]] / [[V2_UNCERTAIN]] | [[V2_LATENCY]] | [[V2_BYTES]] |
| V3: scene 전·후 | [[V3_ACTION_ACC]] / [[V3_ACTION_SELECTIVE_ACC]] | [[V3_CATEGORY_ACC]] | [[V3_NAME_ACC]] | [[V3_COVERAGE]] / [[V3_UNCERTAIN]] | [[V3_LATENCY]] | [[V3_BYTES]] |
| V4: scene+crop 전·후 | [[V4_ACTION_ACC]] / [[V4_ACTION_SELECTIVE_ACC]] | [[V4_CATEGORY_ACC]] | [[V4_NAME_ACC]] | [[V4_COVERAGE]] / [[V4_UNCERTAIN]] | [[V4_LATENCY]] | [[V4_BYTES]] |

¹ Action 정확도는 GT-added [[N_VLM_GT_ADDED]]개와 GT-removed [[N_VLM_GT_REMOVED]]개의 decisive 표본에서 계산하고 uncertain을 오답으로 처리한다. Category와 물품 의미 정확도는 GT-added에만 계산한다.

non-removal/retain [[N_VLM_RETAIN]]개를 포함한 운영 결정 평가에서 added 경로의 register/hold 정확도는 [[VLM_REGISTER_DECISION_ACC]], verify_removed 경로의 recover 결정 정확도는 [[VLM_RECOVER_DECISION_ACC]], retain 안전률은 [[VLM_RETAIN_SAFETY_ACC]]였다.

전체 [[TOTAL_MONITORED_EPISODES]]개 감시 episode 중 로컬 변화 사건은 [[LOCAL_EVENT_COUNT]]개였고 logical VLM job은 [[VLM_CALL_COUNT]]개로, episode당 호출률은 [[VLM_CALL_RATE]]였다. GT-added gate recall은 [[VLM_GATE_RECALL_ADDED_CI]], 사전 라벨된 모호 제거 [[N_GT_AMBIGUOUS_REMOVAL]]개에 대한 gate recall은 [[VLM_GATE_RECALL_REMOVAL_CI]]였다. 운영 auto provider의 fallback을 포함한 HTTP attempt는 [[VLM_ATTEMPT_COUNT]]회, 성공 응답은 [[VLM_SUCCESS_COUNT]]회였다. analyzing에 도달한 모든 episode의 전체 장면 전후를 보내는 no-gating 기준선 대비 직렬화 payload byte 변화는 [[TRANSFER_REDUCTION_RESULT]]였고, 모든 처리 frame 전송 대비 값 [[ALL_FRAME_TRANSFER_UPPER_BOUND]]은 실측이 아닌 분석적 상한으로 구분하였다. 비용은 provider attempt 원장에 근거해 episode당 [[COST_PER_EPISODE]]원, attempt당 [[COST_PER_ATTEMPT]]원으로 계산하였다.

[[RESULT_VLM_INTERPRETATION]] V4가 최고가 아닐 경우 “4장이 우수하다”는 결론을 삭제하고, 관찰된 최적 증거 구성을 최종 정책으로 제안한다. 모델 응답의 의미 평가는 두 평가자의 합의 기준, 동의도와 허용 동의어 목록을 함께 보고한다. 로컬 누락과 DB 반영까지 포함한 \(D_{stream}\)의 종단간 업무 성공률은 전체 [[END_TO_END_TASK_SUCCESS]], added [[TASK_SUCCESS_ADDED_CI]], moved [[TASK_SUCCESS_MOVED_CI]], removed [[TASK_SUCCESS_REMOVED_CI]], 세 종류 macro [[TASK_SUCCESS_MACRO_CI]]였다.

## 6-5. 실패 사례, 운영 안정성과 한계

**표 12. 실패 사례 분류 / Table 12. Taxonomy of failure cases**

| 실패 범주 | N | FP | FN/오분류 | 대표 원인과 개선 방향 |
|---|---:|---:|---:|---|
| 노출·색온도 변화 | [[FAIL_EXPOSURE_N]] | [[FAIL_EXPOSURE_FP]] | [[FAIL_EXPOSURE_FN]] | [[FAIL_EXPOSURE_NOTE]] |
| 그림자·반사 | [[FAIL_SHADOW_N]] | [[FAIL_SHADOW_FP]] | [[FAIL_SHADOW_FN]] | [[FAIL_SHADOW_NOTE]] |
| 미세진동·초점 | [[FAIL_JITTER_N]] | [[FAIL_JITTER_FP]] | [[FAIL_JITTER_FN]] | [[FAIL_JITTER_NOTE]] |
| 소형·저대비 물품 | [[FAIL_SMALL_N]] | [[FAIL_SMALL_FP]] | [[FAIL_SMALL_FN]] | [[FAIL_SMALL_NOTE]] |
| 가림·겹침·동시 행동 | [[FAIL_OCCLUSION_N]] | [[FAIL_OCCLUSION_FP]] | [[FAIL_OCCLUSION_FN]] | [[FAIL_OCCLUSION_NOTE]] |
| settling 실패 | [[FAIL_SETTLING_N]] | [[FAIL_SETTLING_FP]] | [[FAIL_SETTLING_FN]] | [[FAIL_SETTLING_NOTE]] |
| 사건 종류 혼동 | [[FAIL_KIND_N]] | [[FAIL_KIND_FP]] | [[FAIL_KIND_FN]] | [[FAIL_KIND_NOTE]] |
| ID 단절·중복 | [[FAIL_ID_N]] | — | [[FAIL_ID_ERROR]] | [[FAIL_ID_NOTE]] |
| 카메라·네트워크·처리 지연 | [[FAIL_SYSTEM_N]] | — | [[FAIL_SYSTEM_ERROR]] | [[FAIL_SYSTEM_NOTE]] |

**표 13. 통제 장애 주입과 안전 상태 보존 / Table 13. Controlled fault injection and safe-state preservation**

| 주입 장애 | 주입 N | 성공 기준 | 결과 |
|---|---:|---|---:|
| DB write 실패 | [[FAULT_DB_WRITE_N]] | 부분·손상 행 없이 오류 기록 | [[FAULT_DB_SAFE_RATE]] |
| VLM timeout | [[FAULT_VLM_TIMEOUT_N]] | 생성된 provisional 행 보존 | [[FAULT_VLM_TIMEOUT_PRESERVATION_RATE]] |
| malformed JSON | [[FAULT_MALFORMED_RESPONSE_N]] | 생성된 provisional 행 보존 | [[FAULT_MALFORMED_RESPONSE_PRESERVATION_RATE]] |
| 원격 작업 queue 포화 | [[FAULT_REMOTE_QUEUE_FULL_N]] | 생성된 provisional 행 보존·확인 필요 표시 | [[FAULT_REMOTE_QUEUE_PRESERVATION_RATE]] |
| change callback queue 포화 | [[FAULT_CALLBACK_QUEUE_FULL_N]] | drop 탐지·계수·진단 기록 | [[FAULT_CALLBACK_DROP_ACCOUNTING_RATE]] |
| 오래된 added 응답 | [[FAULT_STALE_ADDED_N]] | 관리자 수정·현재 상태 덮어쓰기 차단 | [[FAULT_STALE_ADDED_BLOCK_RATE]] |
| 오래된 verify_removed 응답 | [[FAULT_STALE_VERIFY_N]] | 변경된 추적 signature의 회수 전환 차단 | [[FAULT_STALE_VERIFY_BLOCK_RATE]] |
| 처리 중 프로세스 재시작 | [[FAULT_PROCESS_RESTART_N]] | DB 일관성 유지와 서비스 복귀 | [[FAULT_RESTART_RECOVERY_RATE]] |

[[LONG_RUN_DURATION_HOURS]]시간 연속 실행에서 카메라 disconnect는 [[CAMERA_DISCONNECT_COUNT]]회였고 reconnect 지연 p50/p95는 [[CAMERA_RECONNECT_P50_MS]]/[[CAMERA_RECONNECT_P95_MS]] ms였다. 서비스 재시작은 [[SERVICE_RESTART_COUNT]]회, DB 오류는 [[DB_ERROR_COUNT]]회, 원격 요청 실패는 [[VLM_FAILURE_COUNT]]회 발생했다. 관찰된 added 실패가 없으면 장시간 실행의 provisional 보존률은 정의하지 않는다. 대신 \(D_{fault}\)의 [[FAULT_INJECTION_CASE_COUNT]]개 통제 장애 중 임시 레코드 보존률 [[PROVISIONAL_PRESERVATION_RATE]]과 유형별 복구 결과를 표 13에 보고한다. drop 값이 0이라도 실험 시간과 부하 범위 안의 관찰일 뿐 완전 무손실을 의미하지 않는다.

본 연구에는 다음 한계가 있다. 첫째, [[SITE_COUNT]]개 장소와 단일 Raspberry Pi·카메라 중심의 평가는 다른 설치 높이, 렌즈와 복잡한 배경으로 일반화하는 데 제한이 있다. 둘째, 규칙 기반 threshold는 환경에 따라 조정이 필요하고, 심한 가림이나 여러 물품의 동시 이동에서는 일대일 대응이 깨질 수 있다. 셋째, 외부 멀티모달 모델의 결과, 지연과 비용은 provider의 모델 갱신과 네트워크 상태에 영향을 받는다. 넷째, 전체 장면 증거에는 사람이 포함될 수 있으므로 실제 배포에서는 촬영 고지, 접근 통제, 보존 기간과 얼굴 비식별화 정책이 필요하다. 다섯째, 운영 보관 기한은 법적 판단이 아니라 시스템 기본값이며 기관 규정에 맞게 검토해야 한다.

# 7. 결론

본 논문은 Raspberry Pi 4 2GB의 고정 카메라에서 물품 상태 변화를 로컬로 선별하고, 의미 판단이 필요한 사건에만 외부 멀티모달 추론을 적용하는 분실물 관리 시스템 Re:Found를 설계·구현하였다. 시스템은 안정 장면 상태기계, 특징 기반 기하 정합, 전역·국소 조명 보정, 지속 경계 흔들림 억제와 활성 물품 참조 비교를 결합하여 added, moved, removed 및 verify_removed 사건을 생성한다. 이동은 기존 ID를 유지하고, 명확한 제거는 로컬에서 처리하며, 신규 등록과 모호한 제거에는 전체 장면 및 crop 전후 증거를 사용한다. callback worker가 정상 접수한 added는 원격 응답 전에 임시 레코드로 저장하고, verify_removed는 추적 signature를 재검사하여 외부 서비스 실패와 비동기 상태 변경에 대응하였다.

평가 결과, [[CONCLUSION_RESULT_1]]. 방해요인 ablation에서는 [[CONCLUSION_RESULT_2]]였고, Raspberry Pi의 자원 및 지연 측정에서는 [[CONCLUSION_RESULT_3]]였다. 선택적 멀티모달 정책은 [[CONCLUSION_RESULT_4]]. 이러한 결과는 [[FINAL_EVIDENCE_BOUNDED_CLAIM]]을 보여준다. 향후 연구에서는 다양한 설치 환경의 다기관 데이터, 동시 다중 물품 대응, 장기 drift 관리와 개인정보 비식별화를 포함해 외적 타당성과 운영 안전성을 확장할 예정이다.

# 참고문헌

[1] H. Jeong, H. Yoo, T. You, Y. Kim, and Y. H. Ahn, “Lost and Found Registration and Inquiry Management System for User-Dependent Interface Using Automatic Image Classification and Ranking System Based on Deep Learning,” Journal of Convergence Security, Vol. 18, No. 4, pp. 19-25, 2018.

[2] H. S. Jang, J. Y. Min, J. S. Kim, S. M. Park, J. H. Shin, D. G. Kim, K. M. Do, and G. S. Yoo, “Implementation of a Deep OC-SORT-Based Multi-Object Tracking and Matching Algorithm for Managing Lost Items and Owners in Trains,” Journal of Korean Institute of Information Technology, Vol. 23, No. 2, pp. 165-176, 2025. https://doi.org/10.14801/jkiit.2025.23.2.165

[3] H.-J. Yang and G.-S. Choi, “Lost-Item Detection in Vehicles Using Histogram Equalization and Contour Filtering,” Proceedings of the 2025 Summer Conference of the Korean Institute of Information Technology, pp. 1221-1224, 2025. https://www.dbpia.co.kr/journal/articleDetail?nodeId=NODE12288829 [[VERIFY_ENGLISH_TITLE_AND_ROMANIZATION]]

[4] H. Park, S. Park, and Y. B. Joo, “Realtime Theft Detection of Registered and Unregistered Objects in Surveillance Video,” Journal of the Korea Institute of Information and Communication Engineering, Vol. 24, No. 10, pp. 1262-1270, 2020. https://doi.org/10.6109/jkiice.2020.24.10.1262

[5] D. Ryu and J.-H. Lee, “The Method of Abandoned Object Recognition Based on Neural Networks,” Journal of Institute of Korean Electrical and Electronics Engineers, Vol. 22, No. 4, pp. 1131-1139, 2018. https://doi.org/10.7471/ikeee.2018.22.4.1131

[6] K.-H. Kim, H.-Y. Yu, H.-J. Lee, and H.-W. Byun, “Automatic Garbage Classification System based on YOLOv4 and Rasberry Pi,” Journal of Digital Contents Society, Vol. 22, No. 12, pp. 2111-2119, 2021. https://doi.org/10.9728/dcs.2021.22.12.2111

[7] S.-W. Park, Y.-J. Park, H.-W. Choi, S.-H. Ha, and Y.-S. Do, “A Study on Real-Time Object Detection Models Suitable for Raspberry Pi,” Proceedings of the 2024 Korea Information Processing Society Conference, Vol. 31, No. 2, pp. 944-945, 2024. https://koreascience.kr/article/CFKO202433161890933.pdf [[VERIFY_ENGLISH_TITLE_AND_ROMANIZATION]]

[8] C. Stauffer and W. E. L. Grimson, “Adaptive Background Mixture Models for Real-Time Tracking,” Proceedings of the IEEE Computer Society Conference on Computer Vision and Pattern Recognition, Vol. 2, pp. 246-252, 1999. https://doi.org/10.1109/CVPR.1999.784637

[9] Z. Zivkovic, “Improved Adaptive Gaussian Mixture Model for Background Subtraction,” Proceedings of the 17th International Conference on Pattern Recognition, Vol. 2, pp. 28-31, 2004. https://doi.org/10.1109/ICPR.2004.1333992

[10] K. Toyama, J. Krumm, B. Brumitt, and B. Meyers, “Wallflower: Principles and Practice of Background Maintenance,” Proceedings of the Seventh IEEE International Conference on Computer Vision, Vol. 1, pp. 255-261, 1999. https://doi.org/10.1109/ICCV.1999.791228

[11] K. Lin, S.-C. Chen, C.-S. Chen, D.-T. Lin, and Y.-P. Hung, “Left-Luggage Detection from Finite-State-Machine Analysis in Static-Camera Videos,” 2014 22nd International Conference on Pattern Recognition, pp. 4600-4605, 2014. https://doi.org/10.1109/ICPR.2014.787

[12] J. Shi and C. Tomasi, “Good Features to Track,” Proceedings of the IEEE Conference on Computer Vision and Pattern Recognition, pp. 593-600, 1994. https://doi.org/10.1109/CVPR.1994.323794

[13] B. D. Lucas and T. Kanade, “An Iterative Image Registration Technique with an Application to Stereo Vision,” Proceedings of the 7th International Joint Conference on Artificial Intelligence, pp. 674-679, 1981.

[14] M. A. Fischler and R. C. Bolles, “Random Sample Consensus: A Paradigm for Model Fitting with Applications to Image Analysis and Automated Cartography,” Communications of the ACM, Vol. 24, No. 6, pp. 381-395, 1981. https://doi.org/10.1145/358669.358692

[15] M. Satyanarayanan, “The Emergence of Edge Computing,” Computer, Vol. 50, No. 1, pp. 30-39, 2017. https://doi.org/10.1109/MC.2017.9

[16] Y. Kang, J. Hauswald, C. Gao, A. Rovinski, T. Mudge, J. Mars, and L. Tang, “Neurosurgeon: Collaborative Intelligence Between the Cloud and Mobile Edge,” Proceedings of the Twenty-Second International Conference on Architectural Support for Programming Languages and Operating Systems, pp. 615-629, 2017. https://doi.org/10.1145/3037697.3037698

[17] E. Li, Z. Zhou, and X. Chen, “Edge Intelligence: On-Demand Deep Learning Model Co-Inference with Device-Edge Synergy,” Proceedings of the 2018 Workshop on Mobile Edge Communications, pp. 31-36, 2018. https://doi.org/10.1145/3229556.3229562

[18] D. Kang, J. Emmons, F. Abuzaid, P. Bailis, and M. Zaharia, “NoScope: Optimizing Neural Network Queries over Video at Scale,” Proceedings of the VLDB Endowment, Vol. 10, No. 11, pp. 1586-1597, 2017. https://doi.org/10.14778/3137628.3137664

[19] Y. Li, A. Padmanabhan, P. Zhao, Y. Wang, G. H. Xu, and R. Netravali, “Reducto: On-Camera Filtering for Resource-Efficient Real-Time Video Analytics,” Proceedings of ACM SIGCOMM 2020, pp. 359-376, 2020. https://doi.org/10.1145/3387514.3405874

[20] J. Li, D. Li, S. Savarese, and S. Hoi, “BLIP-2: Bootstrapping Language-Image Pre-training with Frozen Image Encoders and Large Language Models,” Proceedings of the 40th International Conference on Machine Learning, Vol. 202, pp. 19730-19742, 2023.

[21] 권영환, “An Augmentation Method for Lost Item Annotation Using BLIP-2,” Master’s thesis, Sogang University Graduate School of Artificial Intelligence and Software, 2025. http://www.dcollection.net/handler/sogang/000000079512 [[VERIFY_AUTHOR_ROMANIZATION]]

[22] Raspberry Pi Ltd., “The Picamera2 Library,” [Online]. Available: https://datasheets.raspberrypi.com/camera/picamera2-manual.pdf (accessed Sep. 15, 2026).

[23] SQLite, “Write-Ahead Logging,” [Online]. Available: https://www.sqlite.org/wal.html (accessed Sep. 15, 2026).

[24] OpenAI, “Create a Model Response,” [Online]. Available: https://developers.openai.com/api/reference/cli/resources/responses/methods/create (accessed Sep. 15, 2026).

[25] Google, “Image Understanding,” Gemini API Documentation, [Online]. Available: https://ai.google.dev/gemini-api/docs/image-understanding (accessed Sep. 15, 2026).

[26] E. Rublee, V. Rabaud, K. Konolige, and G. Bradski, “ORB: An Efficient Alternative to SIFT or SURF,” 2011 International Conference on Computer Vision, pp. 2564-2571, 2011. https://doi.org/10.1109/ICCV.2011.6126544

---

# 투고본에서 제거할 편집 메모

1. 초록과 6·7장의 모든 이중 대괄호 값을 RESULTS_FILL_SHEET.md와 실제 CSV 집계값으로 교체한다.
2. Figure 1은 docs/presentation/diagrams/01-system-architecture.mmd를 논문용으로 단순화해 SVG 또는 300 dpi 이상 PNG로 다시 출력한다.
3. Figure 2~4는 코드 흐름과 실제 실험 예시 영상으로 새로 제작한다. 사람 얼굴과 화면 속 개인정보는 비식별화한다.
4. 심사용 원고에서는 저자, 소속, 지도교수와 감사의 글을 제거한다.
5. JDCS 공식 HWP 양식으로 옮길 때 장·절 번호, 국·영문 표/그림 캡션, 2단 배치와 참고문헌 영문 표기를 재점검한다.
6. [3], [7], [21]의 영문 제목 또는 로마자 저자명은 공식 발행 메타데이터나 저자에게 확인한다.
7. 코드의 회귀 test 수는 실행 시점에 다시 측정하며, 실제 인식 성능과 혼동하지 않는다.
8. 실제 결과가 가설과 다르면 결과에 맞추어 초록·결론을 수정한다. 빈칸을 “우수”, “실시간”, “저전력” 같은 정성 표현으로 덮지 않는다.
9. 9~10쪽 조판본에서는 표 3·4를 합치고, 표 9·12·13의 실패·장애 정보를 통합하거나 일부를 보조자료로 옮기며, 그림 1·2를 한 장으로 합친다. 알고리즘 1은 지면이 부족하면 삭제하고 본문을 25~30% 줄인다.
10. 표 7의 (a)·(b)는 하나의 복합 표로 조판하고, 7열인 표 11은 전폭 배치하거나 action 결과와 운영 비용 표로 분할한다.
