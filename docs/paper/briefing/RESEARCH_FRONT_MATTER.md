# 저사양 엣지 장치에서의 사건 기반 장면 변화 감지와 선택적 멀티모달 추론을 이용한 분실물 관리 시스템

An Event-Triggered Scene Change Detection and Selective Multimodal Inference System for Lost-Item Management on a Resource-Constrained Edge Device

## 요약

분실물 보관대의 자동 관리는 물품의 종류를 인식하는 것과 함께 물품이 새로 놓이거나 이동하고 사라지는 상태 변화를 기록해야 한다. 그러나 고정 카메라에서도 조명 변화, 그림자, 초점 변화와 미세진동이 물품 변화와 유사한 영상 차이를 만들며, 제한된 연산 자원에서 지속적인 영상 분석과 관리 서비스를 함께 수행해야 하는 문제가 있다. 본 연구는 Raspberry Pi 4 2GB에서 사건 기반 장면 변화 감지와 선택적 멀티모달 추론을 결합한 분실물 관리 시스템 Re:Found를 설계하고 구현하였다. 로컬에서는 움직임 종료와 장면 안정화를 확인한 뒤 영상 정합, 조명 보정 및 기존 물품과의 대응을 통해 추가·이동·제거 후보를 판단한다. 신규 물품과 제거 여부가 모호한 경우에는 전체 장면과 변화 영역의 전후 이미지를 외부 시각언어모델에 전달한다. 정상 접수된 신규 사건은 원격 추론 전에 임시 저장하고, 인식 결과를 보관 기한과 상태 변경 이력에 연결한다. 본 연구는 저사양 장치의 사건 선별과 외부 의미 추론을 분담하는 시스템 구성에 초점을 두며, 향후 사건 검출 성능, 처리 지연, 자원 사용량과 외부 호출량을 평가할 계획이다.

주제어: 엣지 컴퓨팅, 장면 변화 감지, 멀티모달 인공지능, 분실물 관리, 라즈베리 파이

## Abstract

Automated management of a lost-item storage area requires recognizing objects and recording whether they have been added, moved, or removed. Even a fixed camera can produce misleading changes because of illumination shifts, shadows, focus variation, and slight vibration. Continuous monitoring must also share limited computing resources with management services. This study presents Re:Found, a system implemented on a Raspberry Pi 4 with 2 GB of memory that combines event-triggered scene change detection with selective multimodal inference. The local pipeline waits for motion to cease and the scene to stabilize, then applies image alignment, illumination compensation, and association with existing items to identify candidate changes. Newly added items and ambiguous removals are referred to an external vision-language model using before-and-after views of the full scene and the candidate region. New-item events accepted by the callback worker are provisionally stored before remote inference, and recognition results are linked to retention periods and status histories. The study focuses on dividing event selection and semantic inference between the edge device and the external model. Future evaluation will examine event detection performance, processing latency, resource consumption, and remote invocation frequency.

Keywords: Edge Computing, Scene Change Detection, Multimodal AI, Lost-Item Management, Raspberry Pi

<!-- PAGEBREAK -->

## 1. 서론

### 1-1 연구 배경과 필요성

학교와 공공시설의 분실물 보관 업무에는 물품의 접수, 특징 기록, 보관 상태 확인과 처리 이력 관리가 함께 요구된다. 사진을 활용한 자동 분류는 등록 정보의 입력을 도울 수 있다. 정하민 등[1]은 단일 사진에서 물품의 분류와 태그를 추출하고 검색 순위를 제공하는 유실물 관리 시스템을 제안하였다. 이 접근은 등록·조회 과정에 초점을 두며, 보관대에서 물품의 상태가 바뀌는 시점을 영상으로 파악하는 문제는 별도로 다룰 필요가 있다.

영상 기반 연구에서는 사람과 소지품의 관계를 추적하여 분실 상황을 판단하기도 한다. 장현상 등[2]은 열차 영상에서 YOLOv8, Deep OC-SORT와 BLIP을 이용하여 사람과 가방의 탐지·추적·매칭 및 외형 설명을 수행하였다. 한편 양형준과 최규상[3]은 Raspberry Pi 4에서 차량 내부의 전후 이미지를 비교하고, MOG2와 히스토그램 평활화 및 윤곽선 필터링으로 분실물 후보를 추출하였다. 이러한 연구들은 사진 기반 등록, 소유 관계 추적, 전후 장면 비교라는 서로 다른 접근을 보여준다.

본 연구의 대상은 담당자가 분실물을 놓아두는 고정된 보관대이다. 이 환경에서는 물품이 놓인 뒤 같은 자리에 유지되는 동안에도 영상이 계속 입력된다. 따라서 분석의 핵심 단위를 개별 프레임에서 물품의 상태가 바뀌는 사건으로 옮기는 구성을 검토할 수 있다. 예를 들어 물품을 옆으로 옮긴 경우에는 신규 물품을 추가하는 대신 기존 기록의 위치를 갱신해야 하며, 조명만 변한 경우에는 물품 사건을 만들지 않아야 한다.

### 1-2 문제 정의

보관대의 상태 변화를 자동으로 기록하려면 영상의 차이와 실제 물품의 변화를 구분해야 한다. 조명이나 그림자는 물품이 그대로 있어도 차이를 만들 수 있으며, 카메라의 작은 흔들림은 기존 물품의 경계를 이동시킨다. Wallflower 연구[4]가 다룬 배경 유지 문제처럼, 영상의 변화량만으로 사건을 판단하기 어려운 조건이 존재한다. 물품을 놓는 손의 움직임과 손이 빠진 뒤 남은 물품의 변화도 구별해야 한다.

또한 물품의 상태 변화 판단과 종류에 대한 설명은 서로 다른 작업이다. 전후 영상에서 변화 위치를 찾았더라도 해당 물품의 이름과 특징을 바로 알 수는 없다. 반대로 모든 프레임의 의미를 외부 모델에 묻는 구성은 요청량과 네트워크 의존성을 고려해야 한다. 이 때문에 저사양 장치가 담당할 사건 선별 범위와 외부 모델에 맡길 의미 판단 범위를 함께 정하는 문제가 중요하다.

### 1-3 연구 목적과 범위

본 연구의 목적은 로컬 장면 변화 감지, 선택적 외부 멀티모달 추론 및 물품 관리 이력을 하나의 시스템으로 연결하는 것이다. 연구 질문은 다음과 같다. 첫째, 안정 장면 분석과 영상 보정은 추가·이동·제거의 검출 성능 및 오탐에 어떤 영향을 주는가. 둘째, 이 과정의 대기시간과 연산 부담은 Raspberry Pi의 처리 지연과 자원 사용량에 어떻게 나타나는가. 셋째, 필요한 사건만 외부 모델에 전달할 때 호출량, 누락과 최종 업무 성공률 사이에 어떤 관계가 있는가.

이를 위해 Raspberry Pi 4 2GB와 CSI 카메라를 사용하는 Re:Found를 구현하였다. 연구 범위는 보관대에 들어온 물품의 시각적 상태 변화와 관리 기록의 연결이며, 소유자의 신원이나 실제 반환 여부를 영상만으로 판정하지 않는다. 기술적 초점은 사건 선별과 의미 추론의 역할 분담 및 운영 과정의 통합에 있다. 현재 시스템 구현을 바탕으로 실험을 준비하고 있으며, 성능과 효율에 관한 결론은 정량 평가 후 제시한다.

<!-- PAGEBREAK -->

## 2. 이론적 배경

### 2-1 장면 변화 감지와 안정 장면

장면 변화 감지는 서로 다른 시점의 영상에서 달라진 영역을 찾는 과정이다. 배경 차감은 현재 영상과 배경 모델의 차이로 전경 후보를 구하고, 차영상은 비교 대상 영상의 화소 차이를 이용한다. 이러한 방법은 물품의 종류를 미리 결정하지 않고도 변화 후보를 찾는 출발점이 된다. 다만 전경 후보가 곧 신규 물품을 의미하는 것은 아니다. 그림자, 반사와 노출 변화도 영상 차이에 포함될 수 있기 때문이다.

Wallflower[4]는 배경 유지 문제를 화소·영역·프레임 수준에서 다루었다. 이는 변화 후보를 해석할 때 국소적인 차이뿐 아니라 장면 전체의 변화도 고려해야 함을 보여준다. Re:Found가 다루는 보관대에서도 새 물품이 놓인 경우와 조명이 바뀐 경우를 같은 사건으로 처리하면 잘못된 등록이 발생할 수 있다. 따라서 변화 영역의 존재뿐 아니라 변화가 발생한 조건과 기존 물품의 상태를 함께 고려해야 한다.

본 연구에서 안정 장면은 움직임이 멈춘 뒤 일정 구간 동안 변화가 작게 유지되는 장면을 뜻한다. 움직임이 있는 동안에는 손이나 물품의 중간 위치가 관찰되지만, 안정된 전후 장면에서는 최종 배치의 차이를 비교할 수 있다. 영상 정합은 카메라 움직임 등으로 어긋난 영상의 좌표를 맞추는 처리이고, 조명 보정은 밝기 차이가 물품 변화 판단에 미치는 영향을 줄이기 위한 처리이다. 이러한 단계의 실제 효과는 보정 요소를 달리하는 비교 실험으로 확인해야 한다.

### 2-2 엣지 컴퓨팅과 선택적 영상 분석

엣지 컴퓨팅은 센서나 데이터 발생 지점 가까이에 연산을 배치하는 접근이다. Satyanarayanan[5]은 장치와 가까운 연산·저장 자원이 응답성과 연결 장애 대응에 기여할 수 있음을 설명하였다. 이 관점에서 카메라와 가까운 장치가 기초 분석을 수행하고, 추가 처리가 필요한 정보만 외부 서비스로 전달하는 구성을 생각할 수 있다. 처리 위치를 나누더라도 실제 지연과 자원 사용량은 장치와 작업 조건에 따라 측정해야 한다.

선택적 영상 분석의 사례로 NoScope[6]는 차이 검출기와 특정 영상·대상에 맞춘 모델을 단계적으로 결합하여 신경망 영상 질의의 연산을 줄였다. Reducto[7]는 카메라에서 저수준 영상 특징을 이용해 프레임을 선별하고, 영상 내용과 목표 정확도에 따라 필터링을 조정하였다. 두 연구는 모든 영상 입력에 동일한 분석을 반복하기보다 필요한 입력을 선별하는 접근의 근거가 된다.

Re:Found는 이러한 선별 관점을 물품의 상태 변화 사건에 적용한다. 로컬 장치는 추가·이동·제거 후보를 판단하고, 외부 모델은 선택된 사건의 의미를 보완한다. 여기서 사건 기반이라는 말은 일반 카메라 영상의 처리 단위를 뜻하며, 별도의 이벤트 카메라 센서를 사용한다는 의미는 아니다. 외부 호출 감소와 정확도 사이의 관계는 제안 시스템에서도 별도로 검증할 대상이다.

### 2-3 멀티모달 추론과 전후 시각 증거

시각언어모델은 이미지와 언어 정보를 연결하여 이미지의 내용을 설명하거나 질문에 답하는 모델이다. BLIP-2[8]는 사전 학습된 이미지 인코더와 대규모 언어모델을 연결하는 학습 구조를 제시하고 이미지에서 텍스트를 생성하는 능력을 보였다. 이는 영상 특징을 자연어 설명과 연결하는 이론적 배경이며, Re:Found에 BLIP-2를 직접 탑재했다는 뜻은 아니다.

분실물 관리에서는 물품이 무엇인지와 장면에서 어떤 상태 변화가 일어났는지를 함께 판단해야 한다. 변화 영역의 확대 이미지는 물품의 외형을, 전체 장면은 위치와 주변 맥락을 제공할 수 있다. 본 연구는 전체 장면 전후와 변화 영역 전후를 최대 네 장의 증거로 구성한다. 이 구성이 단일 이미지보다 유리한지는 향후 같은 사건에 대한 증거 구성 비교로 평가하며, 불확실한 응답을 운영 상태에 반영하는 방식도 함께 고려한다.

<!-- PAGEBREAK -->

### 2-4 관련 연구와 본 연구의 위치

사진 기반 등록[1], 사람과 물품의 관계 추적[2], 차량 내부 전후 비교[3]는 분실물 관리의 서로 다른 작업을 다룬다. NoScope[6]와 Reducto[7]는 영상 분석에서 입력을 선별하는 전략을 제시하였다. 본 연구는 이들 접근을 참고하여 고정 보관대의 상태 변화, 선택적 의미 추론과 운영 기록의 연결에 초점을 둔다. 표 1은 성능 순위가 아니라 각 연구의 대상과 접근을 비교한 것이다.

표 1. 관련 연구의 대상과 본 연구의 초점
Table 1. Research targets and the focus of this study

| 연구 | 주요 대상과 접근 | 본 연구에서 집중하는 문제 |
|---|---|---|
| 정하민 등[1] | 사진 기반 분류와 등록·조회 | 영상에서 등록 시점 선별 |
| 장현상 등[2] | 사람·가방 추적과 소유 관계 매칭 | 보관대 물품의 상태 변화 |
| 양형준·최규상[3] | 차량 전후 이미지의 변화 후보 | 연속 감시 중 추가·이동·제거 |
| NoScope[6]·Reducto[7] | 고비용 영상 분석 전 입력 선별 | 사건 증거와 외부 의미 추론의 연결 |
| Re:Found | 로컬 사건 선별과 선택적 외부 추론 | 감지부터 물품 관리 이력까지 통합 |

본 연구의 기여는 안정 장면을 이용한 사건 선별, 선택적 의미 추론 및 물품 관리 이력을 연결하는 시스템 구성에 있다. 특히 오탐 억제와 지연, 외부 호출 감소와 사건 누락의 관계를 함께 평가한다. 관련 연구와 데이터·장치·평가 단위가 다르므로 문헌의 정확도를 직접 비교하지 않으며, 동일 영상에 적용한 비교 구성으로 설계의 효과와 한계를 확인한다.

## 참고문헌

[1] H. Jeong, H. Yoo, T. You, Y. Kim, and Y. H. Ahn, “Lost and Found Registration and Inquiry Management System for User-dependent Interface using Automatic Image Classification and Ranking System based on Deep Learning,” Journal of Convergence Security, Vol. 18, No. 4, pp. 19-25, 2018. https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART002401814

[2] H. S. Jang et al., “Implementation of a Deep OC-SORT based Multi-Object Tracking and Matching Algorithm for Managing Lost Items and Owners in Trains,” Journal of Korean Institute of Information Technology, Vol. 23, No. 2, pp. 165-176, 2025. https://doi.org/10.14801/jkiit.2025.23.2.165

[3] 양형준, 최규상, “히스토그램 평활화 및 윤곽선 필터링을 활용한 차량 내 분실물 감지 시스템,” 한국정보기술학회 하계종합학술대회 논문집, pp. 1221-1224, 2025. https://www.dbpia.co.kr/journal/articleDetail?nodeId=NODE12288829

[4] K. Toyama, J. Krumm, B. Brumitt, and B. Meyers, “Wallflower: Principles and Practice of Background Maintenance,” Proceedings of ICCV, Vol. 1, pp. 255-261, 1999. https://doi.org/10.1109/ICCV.1999.791228

[5] M. Satyanarayanan, “The Emergence of Edge Computing,” Computer, Vol. 50, No. 1, pp. 30-39, 2017. https://doi.org/10.1109/MC.2017.9

[6] D. Kang, J. Emmons, F. Abuzaid, P. Bailis, and M. Zaharia, “NoScope: Optimizing Neural Network Queries over Video at Scale,” Proceedings of the VLDB Endowment, Vol. 10, No. 11, pp. 1586-1597, 2017. https://doi.org/10.14778/3137628.3137664

[7] Y. Li, A. Padmanabhan, P. Zhao, Y. Wang, G. H. Xu, and R. Netravali, “Reducto: On-Camera Filtering for Resource-Efficient Real-Time Video Analytics,” Proceedings of ACM SIGCOMM, pp. 359-376, 2020. https://doi.org/10.1145/3387514.3405874

[8] J. Li, D. Li, S. Savarese, and S. Hoi, “BLIP-2: Bootstrapping Language-Image Pre-training with Frozen Image Encoders and Large Language Models,” Proceedings of ICML, PMLR, Vol. 202, pp. 19730-19742, 2023. https://proceedings.mlr.press/v202/li23q.html
