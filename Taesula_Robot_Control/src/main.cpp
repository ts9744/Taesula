#include <Arduino.h>
#include <esp_system.h>

// 리셋 원인 이름 (setup 에서 READY 앞에 출력)
const char* resetReasonName(esp_reset_reason_t r) {
  switch (r) {
    case ESP_RST_POWERON:   return "POWERON";    // 전원 켬 / EN 핀 / 시리얼 포트 열기(DTR/RTS)
    case ESP_RST_EXT:       return "EXT";
    case ESP_RST_SW:        return "SW";         // ESP.restart()
    case ESP_RST_PANIC:     return "PANIC";      // 펌웨어 오류로 죽음 (Guru Meditation)
    case ESP_RST_INT_WDT:   return "INT_WDT";    // 인터럽트 워치독
    case ESP_RST_TASK_WDT:  return "TASK_WDT";   // loop 가 너무 오래 멈춤
    case ESP_RST_WDT:       return "WDT";
    case ESP_RST_DEEPSLEEP: return "DEEPSLEEP";
    case ESP_RST_BROWNOUT:  return "BROWNOUT";   // 전압 부족
    default:                return "UNKNOWN";
  }
}

// =====================================================================
// Taesula ESP32 - 초음파 4방향 + 이동 중 stop + 엔코더 측정 (2026-11-15)
//
// [엔코더]
//   - 바퀴 4개 C1 펄스를 셈 (방향은 모름, 돈 양만)
//   - 이동 끝날 때마다 DONE/OBSTACLE 바로 앞에 출력:
//       ENC FL 820 FR 905 RL 760 RR 910
//       ENC% FL 90 FR 99 RL 84 RR 100
//       SUGGEST FL_TRIM 0.93 FR_TRIM 0.84 RL_TRIM 1.00 RR_TRIM 0.83
//   - enc / enc reset : 손으로 바퀴 돌려서 배선 확인
//   - 실제 주행 땐 PRINT_ENCODER = false 추천
//
// 기존 main_motor_test.cpp 에서 바뀐 점
//   1) 초음파 4개: 가는 방향의 센서 1개만 켜서 감시
//        forward -> 앞 / backward -> 뒤 / left -> 왼쪽 / right -> 오른쪽
//   2) 이동 중에도 시리얼을 읽음: "stop" 이 오면 바로 정지
//        (AI HAT 카메라가 장애물을 보면 라즈베리파이가 stop 을 보내는 용도)
//   3) dist  : 4개 거리를 한 줄로 출력
//      scan  : 4개 거리를 0.2초마다 20번 출력 (센서 고정 위치 확인용, stop 으로 중단)
//   4) sonar on / sonar off : 이동 중 감지 켜기/끄기 (리셋하면 다시 ON)
//
// 모터 핀 / INV / TRIM / 속도 / 이동 시간은 기존 코드와 같음
// 라즈베리파이 통신 형식(DONE / OBSTACLE)도 같음
// =====================================================================

// 테스트용 LED
const int LED_PIN = 15;   // 2026-11-15: GPIO2 를 FL_IN2 로 쓰게 돼서 LED 표시는 빈 핀(15)으로 (실제 LED 없음)

// ===============================
// 초음파 센서 4개
// 번호: 0 = 앞, 1 = 왼쪽, 2 = 뒤, 3 = 오른쪽
// ECHO 는 모두 분압(저항) 거쳐서 들어옴
// ===============================
const int SONAR_COUNT = 4;
const int S_FRONT = 0;
const int S_LEFT  = 1;
const int S_BACK  = 2;
const int S_RIGHT = 3;

const char* SONAR_NAME[SONAR_COUNT] = {"front", "left", "back", "right"};
const int   TRIG_PINS[SONAR_COUNT]  = {5,  4,  21, 13};   // P5, P4, P21, P13
const int   ECHO_PINS[SONAR_COUNT]  = {18, 34, 39, 35};   // P18, P34, SVN(39), P35

// ===============================
// 엔코더 C1 (VCC = 3.3V 레일, GND = − 레일, C2 는 안 씀)
// 순서: FL, FR, RL, RR
// ===============================
const int ENC_COUNT = 4;
const char* WHEEL_NAME[ENC_COUNT] = {"FL", "FR", "RL", "RR"};
const int   ENC_PINS[ENC_COUNT]   = {27, 33, 14, 36};   // P27, P33, P14, SVP(36)
const unsigned long ENC_MIN_GAP_US = 200;                // 너무 짧은 간격 펄스는 노이즈로 무시
bool PRINT_ENCODER = false;                              // debug on 으로 켜기 (시연 땐 off)

volatile unsigned long encCount[ENC_COUNT] = {0, 0, 0, 0};
volatile unsigned long encLastUs[ENC_COUNT] = {0, 0, 0, 0};

void IRAM_ATTR encTick(int i) {
  unsigned long now = micros();
  if (now - encLastUs[i] >= ENC_MIN_GAP_US) {
    encCount[i]++;
    encLastUs[i] = now;
  }
}
void IRAM_ATTR encIsrFL() { encTick(0); }
void IRAM_ATTR encIsrFR() { encTick(1); }
void IRAM_ATTR encIsrRL() { encTick(2); }
void IRAM_ATTR encIsrRR() { encTick(3); }

// ===============================
// ZK-BM1 #1 : 앞바퀴
// ===============================
const int FL_IN1 = 25;
const int FL_IN2 = 2;    // 2026-11-15: P26 경로 고장 -> P2 (ESP32 빵판 j21) 로 옮김

const int FR_IN1 = 32;
const int FR_IN2 = 19;

// ===============================
// ZK-BM1 #2 : 뒷바퀴
// ===============================
// 드라이버 #2 출력에서 뒤 모터 좌우가 바뀌어 연결되어 코드에서 맞바꿈
//   P22/P23 (드라이버 #2 IN3/IN4) -> 뒤-왼쪽 바퀴
//   P16/P17 (드라이버 #2 IN1/IN2) -> 뒤-오른쪽 바퀴
const int RL_IN1 = 22;
const int RL_IN2 = 23;

const int RR_IN1 = 16;
const int RR_IN2 = 17;

// ===============================
// 모터 방향 보정 (바퀴가 반대로 돌면 그 모터만 true/false 바꾸기)
// ===============================
const bool FL_INV = false;   // 2026-11-12: 재배선 후 FL이 거꾸로 돌아서 true -> false
const bool FR_INV = true;
const bool RL_INV = false;
const bool RR_INV = true;

// ===============================
// 이동 설정
// ===============================
// [2026-11-19] 한 칸 = 34cm. 실측 후 값 확정 -> robot_bridge.py FORWARD_RUN_MS 도 같은 값으로
const unsigned long FORWARD_RUN_MS = 1000;   // 1칸 이동 시간 (전진/후진)
const unsigned long STRAFE_RUN_MS  = 1000;   // 1칸 이동 시간 (좌/우) - 따로 실측

// 명령마다 감속+브레이크로 더 가는 거리를 시간으로 빼주기 (1칸/3칸 실측으로 계산, 처음엔 0)
const unsigned long FORWARD_OVERSHOOT_MS = 0;
const unsigned long STRAFE_OVERSHOOT_MS  = 0;

// ===============================
// [2026-11-19] 엔코더로 거리 재기 (시간 대신 펄스로 칸 세기)
//   - 4바퀴 평균 펄스가 목표에 닿으면 멈춤 (안 들어오는 바퀴는 빼고 평균)
//   - 엔코더가 다 안 들어오면 그 이동은 자동으로 시간 방식(RUN_MS)으로 돌아감
//   - 보정: debug on -> forward 3 -> 'ENCAVG' 의 got 값 / 실제 거리(cm) = PULSES_PER_CM
//           멈춘 뒤 목표보다 더 간 만큼(got - target 평균)을 STOP_EARLY_PULSES 에
//   - OBSTACLE/STOPPED 의 ms 값은 '펄스를 RUN_MS 기준 시간으로 환산한 값' (브릿지 그대로 사용 가능)
// ===============================
bool USE_ENC_DIST = true;                 // encdist on/off 로 바꿀 수 있음
const float CELL_CM = 34.0;
const float PULSES_PER_CM_FWD    = 31.8;  // 2026-11-21 실측: forward 3 -> 3145펄스 / 99cm (backward 3 도 99cm)
const float PULSES_PER_CM_STRAFE = 32.3;  // 2026-11-19 실측: right 2 -> 약 3989펄스 / 평균 123.5cm
const long  STOP_EARLY_PULSES_FWD    = 373; // 브레이크 후 관성: 3145 - (3182 - 410) = 373
const long  STOP_EARLY_PULSES_STRAFE = 265; // 2026-11-19: right 69~69.5 / left 70cm -> 1.5cm 줄임

long  gTargetPulses = 0;      // 0 이면 시간 방식
long  gStopEarly = 0;
float gPulsesPerCell = 1;
unsigned long gRunMs = 1000;
bool  gUsedEnc = false;       // 이번 이동이 실제로 엔코더 방식으로 끝났는지

// ===============================
// [2026-11-19] 제자리 회전 (AprilTag 방향 보정용)
//   rotate 5  -> 오른쪽(시계)으로 5도 / rotate -5 -> 왼쪽으로 5도
//   엔코더 4바퀴 평균 펄스로 각도를 셈. 응답: DONE rotate <각도>
//   보정: rotate 360 -> 실제로 돈 각도 A 측정 -> 새 값 = 지금 값 x 360 / A
//         작은 각도(rotate 5)가 덜 돌면 ROTATE_STOP_EARLY 를 줄이고, 더 돌면 늘리기
// ===============================
const float ROTATE_PULSES_PER_DEG = 8.54;   // 2026-11-21: rotate 90(target 709)->90도, rotate 15(target 26)->10도 두 점으로 맞춤
const int   ROTATE_SPEED = 200;             // 너무 낮으면 작은 각도에서 안 움직임
const long  ROTATE_STOP_EARLY = 59;         // 최소 회전 약 7도 x 8.54
const int   ROTATE_MAX_DEG = 180;

// [팀원 3035c71 반영] 출발 전 장애물 점검
//   가는 방향 센서로 3번 재서 가운데 값이 BLOCK_DISTANCE_CM 이하면 출발하지 않고
//   OBSTACLE <방향> 0 0 <거리> 로 보고 (칸 34cm 기준: 다음 칸 장애물 -> 37cm)
const long BLOCK_DISTANCE_CM[SONAR_COUNT] = {37, 41, 37, 41};   // front, left, back, right
const int  PRECHECK_SAMPLES = 3;

// [2026-11-19] 장애물로 멈춘 뒤 칸 중앙으로 복귀
//   이번 칸에서 움직인 ms 만큼 반대 방향으로 이동 -> 칸 중앙에서 OBSTACLE 출력
//   복귀 후 중앙보다 '뒤'에 서면 RETURN_TRIM_MS 를 올리고, '앞'에 서면 내리기
const bool RETURN_TO_CENTER = true;
const unsigned long RETURN_TRIM_MS = 100;    // 복귀 감속 구간에서 더 가는 만큼 빼기
const unsigned long RETURN_MIN_MS  = 60;     // 이보다 짧으면 복귀 안 함

// 다음 칸 중앙까지 이만큼(ms) 이내로 남았는데 장애물에 걸리면 되돌아가지 않고 그 칸 도착으로 처리
const unsigned long SNAP_FORWARD_MS = 300;   // 약 10cm
const float SNAP_MIN_GAP_CM = 2.0;           // 다음 칸 중앙에 섰을 때 장애물까지 최소 여유

const int MOTOR_SPEED  = 255;
const int STRAFE_SPEED = 255;

// 바퀴별 속도 보정 (1.00 = 그대로, 0.95 = 5% 느리게)
const float FL_TRIM = 0.91;   // 2026-11-15: 엔코더 측정으로 RL(가장 느림)에 맞춤
const float FR_TRIM = 0.74;   // 2026-11-21: forward 1 에서 왼쪽으로 2cm 휨 (왼쪽 펄스 1.1% 적음) -> 오른쪽 0.01 낮춤
const float RL_TRIM = 1.00;
const float RR_TRIM = 0.72;   // 2026-11-21: FR 과 같이 0.01 낮춤

// ===============================
// 좌우 이동(left/right) 전용 보정 - 직진 값과 따로
//   left/right 2 하고 나오는 SUGGEST(strafe) 값을 여기에 넣기
//   눈으로 맞출 때:
//     right 가 오른쪽 '위(앞)'로 뜨고 left 가 왼쪽 '아래(뒤)'로 처지면 -> SFL, SRR 을 0.03 씩 낮추기
//     right 가 오른쪽 '아래(뒤)'로 처지고 left 가 왼쪽 '위(앞)'로 뜨면 -> SFR 을 0.03 씩 낮추기
//   (RL 은 이미 가장 느려서 1.00 고정)
// ===============================
const float SFL_TRIM = 0.81;   // 2026-11-15: 엔코더 + 눈으로 맞춤
const float SFR_TRIM = 0.81;
const float SRL_TRIM = 1.00;
const float SRR_TRIM = 0.87;

// ===============================
// 왼쪽 이동(left) 전용 보정 - right 는 위 S... 값, left 는 아래 L... 값
//   left 가 왼쪽 '아래(뒤)'로 처지면 -> LFL, LRR 을 0.02~0.03 씩 낮추기
//   left 가 왼쪽 '위(앞)'로 뜨면     -> LFL, LRR 을 0.02~0.03 씩 올리기
// ===============================
const float LFL_TRIM = 0.78;
const float LFR_TRIM = 0.78;
const float LRL_TRIM = 1.00;
const float LRR_TRIM = 0.80;

// ===============================
// [2026-11-21] 후진(backward) 전용 보정 - 전진 FL_TRIM~RR_TRIM 과 따로
//   같은 TRIM 으로 전진은 ENC% 95~100 인데 후진은 FR/RR 이 91~92 (모터 역회전 효율 차이) -> 후진 때 휨
//   초기값: 2026-11-21 backward 1 x3 의 SUGGEST 평균
//   debug on -> backward 1 하면 SUGGEST(back) 로 다음 값을 알려 줌
//   눈으로 맞출 때 (휘는 쪽 = 덜 도는 쪽):
//     후진하며 오른쪽으로 휘면 -> BFL, BRL 을 0.02~0.03 씩 낮추기
//     후진하며 왼쪽으로 휘면   -> BFR, BRR 을 0.02~0.03 씩 낮추기
// ===============================
const float BFL_TRIM = 0.82;   // 2026-11-21: backward 3 에서 오른쪽 3cm -> 0.84 에서 0.02 낮춤
const float BFR_TRIM = 0.75;
const float BRL_TRIM = 0.92;   // 2026-11-21: 같이 0.02 낮춤
const float BRR_TRIM = 0.73;

// ===============================
// [2026-11-21] 이동 한 번에 얼마나 돌았는지 엔코더로 어림 (debug on 일 때 TURN 줄 출력)
//   전진/후진: 왼쪽(FL+RL) - 오른쪽(FR+RR) 평균 펄스 차이 / 좌우 바퀴 간격
//   좌우 이동: 앞(FL+FR) - 뒤(RL+RR) 평균 펄스 차이 / 앞뒤 바퀴 간격
//   brake = 감속 시작 순간(sync 가 돌던 구간), end = 완전히 선 뒤(감속·관성 포함)
//   -> brake 는 작은데 end 가 크면 감속/관성 구간에서 틀어지는 것
//   바퀴 간격을 0 으로 두면 각도는 안 찍고 cm 차이만 찍음 (바퀴 중심 사이를 자로 재서 넣기)
// ===============================
const float TRACK_CM     = 0;   // 왼쪽 바퀴 중심 ~ 오른쪽 바퀴 중심
const float WHEELBASE_CM = 0;   // 앞 바퀴 중심 ~ 뒤 바퀴 중심

// ===============================
// 이동 중 장애물 감지
// ===============================
const float STOP_DISTANCE_FB_CM = 15.0;   // 앞/뒤 센서
const float STOP_DISTANCE_LR_CM = 15.0;   // 좌/우 센서 (칸 중앙에서 옆 칸 경계 10.5cm)
const unsigned long SENSOR_INTERVAL_MS = 50;    // 이동 중 측정 간격
const int CONFIRM_COUNT = 2;                    // 연속 2번 이하일 때만 정지 (튀는 값 무시)
bool PRINT_DISTANCE = false;                    // debug on 으로 켜기 (시연 땐 off)
const unsigned long MOVE_TIMEOUT_US = 6000;     // 이동 중엔 약 1m 까지만 측정 (빨리 끝나게)
const unsigned long DIST_TIMEOUT_US = 30000;    // dist/scan 땐 약 5m 까지

// 멈출 때 브레이크 (IN1=IN2=HIGH) 거는 시간. 짐이 미끄러지면 80, 그래도 틀어지면 250
// 멈추는 방법 (2026-11-15 변경)
//   1) RAMP_MS 동안 4바퀴를 같은 비율로 같이 감속 (서는 시점을 맞춤)
//   2) 그 다음 BRAKE_MS 동안 짧게 브레이크
//   멈출 때 아직 틀어지면 RAMP_MS 를 250~300 으로, 짐이 쏠리면 150 으로
const unsigned long RAMP_MS  = 200;
const int           RAMP_STEPS = 10;
const unsigned long BRAKE_MS = 250;            // 감속 후 브레이크 (이미 거의 멈춘 상태라 드라이버 부담 작음)
const unsigned long EMERGENCY_BRAKE_MS = 120;  // 장애물/stop 급정지 때 (감속 없이 바로라 짧게)
bool motorsRunning = false;
float speedScale = 1.0;               // 감속 중에만 1.0 -> 0 으로 내려감
float baseScale  = 1.0;               // nudge 때만 NUDGE_SPEED_SCALE (감속은 이 속도 기준으로 한다)

// [2026-11-22] nudge(AprilTag 보정용 짧은 이동)
//   예전: 목표 펄스가 STOP_EARLY(앞뒤 373 = 11.7cm, 좌우 265 = 8.2cm)보다 작으면 STOP_EARLY+1 로 올려서
//         3cm 든 8cm 든 '최고 속도로 출발하자마자 감속' 하는 같은 동작이 됐다 (실측 fb 3/8cm -> 둘 다 약 6cm, lr 은 거의 안 감).
//         출발 순간 바퀴마다 도는 시점이 달라 sync 가 맞추기 전에 끝나서 틀어졌다.
//   지금: 느린 속도로 가고, 느린 속도에 맞는 작은 STOP_EARLY 를 쓴다
//   튜닝: nudge forward 3 / 6 / 10, nudge right 3 / 6 을 줄자로 재서
//         - 바퀴 하나라도 안 돌거나 옆이동이 안 되면 NUDGE_SPEED_SCALE 을 0.05 씩 올림
//         - 명령보다 더 가면 NUDGE_STOP_EARLY_* 를 올리고, 덜 가면 내림 (1cm 당 약 32펄스)
const float NUDGE_SPEED_SCALE      = 0.6;
const long  NUDGE_STOP_EARLY_FWD    = 100;
const long  NUDGE_STOP_EARLY_STRAFE = 80;
void (*currentAction)() = nullptr;    // 지금 실행 중인 이동 (감속할 때 다시 호출)

bool sonarEnabled = true;   // sonar off 로 끌 수 있음. 리셋하면 다시 ON

// ===============================
// [2026-11-15] 엔코더 실시간 속도 맞추기 (sync)
//   이동 중 SYNC_MS 마다 4바퀴 누적 펄스를 비교해서
//   뒤처진 바퀴는 PWM 올리고, 앞선 바퀴는 내림 -> 4바퀴가 같은 양만큼 돌게
//   - sync on / sync off 명령으로 켜고 끄기 (리셋하면 ON)
//   - 엔코더 하나라도 안 들어오면 그 이동은 자동으로 sync 끔 (SYNC OFF 출력)
//   - 흔들리면(바퀴가 번갈아 울컥) SYNC_KP 를 0.5 로, 효과가 약하면 1.5 로
// ===============================
bool syncEnabled = true;
const unsigned long SYNC_MS       = 50;    // 보정 주기
const unsigned long SYNC_START_MS = 150;   // 출발 직후는 보정 안 함 (가속 구간)
const float SYNC_KP     = 1.0;             // 펄스 1개 차이당 PWM 몇 만큼 보정
const int   SYNC_MAX_ADJ = 60;             // 보정 최대치 (PWM)
int  syncAdj[4] = {0, 0, 0, 0};
// [2026-11-21] 감속(RAMP_MS) 중에도 sync 계속 (예전엔 감속 시작 때 보정값이 고정돼서 마지막에 조금씩 돌았음)
//   debug on 의 TURN 줄에서 end - brake 차이가 줄어드는지 보고, 이상하면 false 로 되돌리기
bool SYNC_DURING_RAMP = true;

// [2026-11-19] 좌우 이동 때 바퀴별 목표 비율 (sync 가 이 비율로 맞춤) 순서: FL, FR, RL, RR
//   sync 는 4바퀴 펄스를 똑같이 맞추는데, 좌우 이동은 롤러가 미끄러져서 펄스가 같아도 비스듬히 감
//   right 가 위(앞)로 뜨면 FL, RR 값을 0.05 씩 낮추기 / 아래(뒤)로 처지면 올리기
//   left  가 아래(뒤)로 처지면 FL, RR 값을 0.05 씩 낮추기 / 위(앞)로 뜨면 올리기
float SYNC_W_RIGHT[4] = {0.95, 1.00, 1.00, 0.95};   // 2026-11-19: right 2 를 3번 해서 평균 3cm 아래로 처져서 0.85 -> 0.90
float SYNC_W_LEFT[4]  = {0.98, 1.00, 1.00, 0.98};   // 2026-11-21: left 2 에서 3cm 위로 떠서 0.90 -> 0.95
// [2026-11-21] 후진 때 바퀴별 목표 비율 (FL, FR, RL, RR). 엔코더는 같게 돌아도 후진하면 오른쪽으로 휨
//   (backward 3: ENC% 99~100, TURN 0.6cm 인데 실제로는 오른쪽 5cm + 3도) -> 왼쪽 바퀴를 조금 덜 돌게
//   더 오른쪽으로 휘면 FL, RL 을 0.01 씩 더 낮추기 / 왼쪽으로 휘면 올리기
float SYNC_W_BACK[4]  = {0.99, 1.00, 0.99, 1.00};
const float SYNC_W_ONE[4] = {1.00, 1.00, 1.00, 1.00};
const float* syncW = SYNC_W_ONE;            // 바퀴별 보정값 FL, FR, RL, RR
bool syncActive = false;

String lineBuf;       // 평소 명령 받는 버퍼
String moveBuf;       // 이동 중 명령 받는 버퍼
String pendingLine;   // 이동 중에 들어온 stop 외 명령 (이동 끝나고 처리)

enum RunResult { RUN_DONE, RUN_OBSTACLE, RUN_STOPPED };


// ===============================
// 함수 선언
// ===============================
void driveMotor(int in1, int in2, bool forward, bool inverted, int speed);
int trimmed(int base, float trim);
void stopMotorPair(int in1, int in2);
void stopMotor();

void moveForward();
void moveBackward();
void strafeLeft();
void strafeRight();

RunResult runTimed(void (*action)(), unsigned long ms, int sensor,
                   unsigned long &ranMs, float &stopDist);
bool pollStopDuringMove();
void handleLine(String line);

float readDistanceCm(int sensor, unsigned long timeoutUs);
void printAllDistances();

void encReset();
void printEncoder(int mode);   // 0 = 전진, 1 = right, 2 = left, 3 = 후진
void printTurn(const unsigned long *atBrake, bool strafe);
void syncCompute();
long encAvg();
void rotateInPlace(int deg);


// 4바퀴 평균 펄스 (최대값의 절반도 안 되는 바퀴 = 선 빠짐으로 보고 제외)
long encAvg() {
  unsigned long c[4], mx = 0;
  for (int i = 0; i < 4; i++) { c[i] = encCount[i]; if (c[i] > mx) mx = c[i]; }
  if (mx == 0) return 0;
  unsigned long sum = 0; int n = 0;
  for (int i = 0; i < 4; i++) if (c[i] * 2 >= mx) { sum += c[i]; n++; }
  return (long)(sum / n);
}

// 제자리 회전 (오른쪽 = 왼쪽 바퀴 전진 + 오른쪽 바퀴 후진)
void rotateInPlace(int deg) {
  bool cw = (deg > 0);
  long target = (long)((cw ? deg : -deg) * ROTATE_PULSES_PER_DEG) - ROTATE_STOP_EARLY;
  if (target < 1) target = 1;

  syncActive = false;
  encReset();
  digitalWrite(LED_PIN, HIGH);
  driveMotor(FL_IN1, FL_IN2,  cw, FL_INV, ROTATE_SPEED);
  driveMotor(RL_IN1, RL_IN2,  cw, RL_INV, ROTATE_SPEED);
  driveMotor(FR_IN1, FR_IN2, !cw, FR_INV, ROTATE_SPEED);
  driveMotor(RR_IN1, RR_IN2, !cw, RR_INV, ROTATE_SPEED);

  unsigned long start = millis();
  unsigned long limit = (unsigned long)target + 1000;          // 엔코더 이상 대비 시간 제한
  bool stopped = false;
  while (encAvg() < target && millis() - start < limit) {
    if (pollStopDuringMove()) { stopped = true; break; }
  }

  currentAction = nullptr;   // 작은 각도라 감속 없이 바로 브레이크
  stopMotor();
  delay(100);

  if (PRINT_ENCODER) {
    Serial.println();
    Serial.print("ROT target ");
    Serial.print(target);
    Serial.print(" got ");
    Serial.println(encAvg());
  }
  if (!stopped && encAvg() < target) {
    Serial.println();
    Serial.println("ROTATE TIMEOUT (엔코더 확인)");
  }
}

// 펄스 -> RUN_MS 기준 시간(ms)으로 환산
unsigned long pulsesToMs(long pulses) {
  if (pulses < 0) pulses = 0;
  return (unsigned long)((float)pulses / gPulsesPerCell * (float)gRunMs);
}


// ===============================
// SETUP
// ===============================
void setup() {
  Serial.begin(115200);
  esp_reset_reason_t rr = esp_reset_reason();
  Serial.println();
  Serial.print("RESET ");
  Serial.print((int)rr);
  Serial.print(' ');
  Serial.println(resetReasonName(rr));
  pinMode(LED_PIN, OUTPUT);

  for (int i = 0; i < SONAR_COUNT; i++) {
    pinMode(TRIG_PINS[i], OUTPUT);
    digitalWrite(TRIG_PINS[i], LOW);
    pinMode(ECHO_PINS[i], INPUT);
  }

  // 엔코더 (GPIO36 은 내부 풀업 없음: RR 이 계속 0 이면 a9 ↔ 3.3V 레일에 10kΩ)
  for (int i = 0; i < ENC_COUNT; i++) {
    pinMode(ENC_PINS[i], (ENC_PINS[i] >= 34) ? INPUT : INPUT_PULLUP);
  }
  attachInterrupt(digitalPinToInterrupt(ENC_PINS[0]), encIsrFL, RISING);
  attachInterrupt(digitalPinToInterrupt(ENC_PINS[1]), encIsrFR, RISING);
  attachInterrupt(digitalPinToInterrupt(ENC_PINS[2]), encIsrRL, RISING);
  attachInterrupt(digitalPinToInterrupt(ENC_PINS[3]), encIsrRR, RISING);

  pinMode(FL_IN1, OUTPUT);
  pinMode(FL_IN2, OUTPUT);
  pinMode(FR_IN1, OUTPUT);
  pinMode(FR_IN2, OUTPUT);
  pinMode(RL_IN1, OUTPUT);
  pinMode(RL_IN2, OUTPUT);
  pinMode(RR_IN1, OUTPUT);
  pinMode(RR_IN2, OUTPUT);

  stopMotor();

  delay(300);

  Serial.println("READY (sonar4 + encoder + sync + encdist + rotate + nudge, sonar ON)");
}


// ===============================
// LOOP
// ===============================
void loop() {
  // 이동 중에 들어왔던 명령이 있으면 먼저 처리
  if (pendingLine.length() > 0) {
    String l = pendingLine;
    pendingLine = "";
    handleLine(l);
  }

  while (Serial.available() > 0) {
    char c = Serial.read();

    if (c == '\n') {
      lineBuf.trim();
      if (lineBuf.length() > 0) {
        String l = lineBuf;
        lineBuf = "";
        handleLine(l);
      }
      lineBuf = "";
    }
    else if (c != '\r') {
      lineBuf += c;
      if (lineBuf.length() > 64) {
        lineBuf = "";
      }
    }
  }
}


// ===============================
// 명령 처리
//
// forward 3 / backward 1 / left 2 / right 1   (라즈베리파이가 보내는 명령)
// stop
// dist            4방향 거리 한 번
// scan            4방향 거리 0.2초마다 20번 (stop 으로 중단)
// sonar on / off  이동 중 감지 켜기/끄기
// fl / fr / rl / rr   바퀴 하나만 1초 전진 테스트
// ===============================
void handleLine(String line) {

  int sp = line.indexOf(' ');

  String dir = (sp == -1) ? line : line.substring(0, sp);
  String arg = (sp == -1) ? "" : line.substring(sp + 1);
  arg.trim();

  dir.toLowerCase();
  arg.toLowerCase();

  int steps = (arg.length() == 0) ? 1 : arg.toInt();


  // -------------------------------
  // 정지
  // -------------------------------
  if (dir == "stop") {
    stopMotor();
    Serial.println("DONE stop 0");
    return;
  }


  // -------------------------------
  // 초음파 감지 켜기/끄기
  // -------------------------------
  // 짧은 위치 보정: nudge <forward|backward|left|right> <cm>  (1~15cm, 가는 방향 센서 확인)
  //   응답: DONE nudge <방향> <cm>  / 막히면 OBSTACLE nudge <방향> 0 0 <거리>
  if (dir == "nudge") {
    int sp2 = arg.indexOf(' ');
    String nd = (sp2 == -1) ? arg : arg.substring(0, sp2);
    int cm = (sp2 == -1) ? 0 : arg.substring(sp2 + 1).toInt();
    if (cm < 1) { Serial.print("DONE nudge "); Serial.print(nd); Serial.println(" 0"); return; }
    if (cm > 15) cm = 15;

    void (*na)() = nullptr;
    int ns = -1;
    bool st = false;
    if (nd == "forward")       { na = moveForward;  ns = S_FRONT; }
    else if (nd == "backward") { na = moveBackward; ns = S_BACK; }
    else if (nd == "left")     { na = strafeLeft;   ns = S_LEFT;  st = true; }
    else if (nd == "right")    { na = strafeRight;  ns = S_RIGHT; st = true; }
    else { Serial.println("ERR unknown " + line); return; }
    if (!sonarEnabled) ns = -1;

    gRunMs = st ? STRAFE_RUN_MS : FORWARD_RUN_MS;
    gPulsesPerCell = CELL_CM * (st ? PULSES_PER_CM_STRAFE : PULSES_PER_CM_FWD);
    gStopEarly = st ? NUDGE_STOP_EARLY_STRAFE : NUDGE_STOP_EARLY_FWD;
    unsigned long nms = (unsigned long)((float)cm / CELL_CM * (float)gRunMs);
    if (USE_ENC_DIST) {
      gTargetPulses = (long)(cm * (st ? PULSES_PER_CM_STRAFE : PULSES_PER_CM_FWD));
      if (gTargetPulses <= gStopEarly) gTargetPulses = gStopEarly + 1;
      nms = (unsigned long)(nms * 2 / NUDGE_SPEED_SCALE) + 500;   // 느리게 가므로 시간 한도도 늘린다
    } else {
      gTargetPulses = 0;
    }

    unsigned long nr = 0;
    float nd2 = -1;
    baseScale = NUDGE_SPEED_SCALE;
    RunResult rr = runTimed(na, nms, ns, nr, nd2);
    baseScale = 1.0;
    Serial.println();
    if (rr == RUN_OBSTACLE) {
      Serial.print("OBSTACLE nudge ");
      Serial.print(nd);
      Serial.print(" 0 0 ");
      Serial.println(nd2, 1);
    } else if (rr == RUN_STOPPED) {
      Serial.println("DONE stop 0");
    } else {
      Serial.print("DONE nudge ");
      Serial.print(nd);
      Serial.print(' ');
      Serial.println(cm);
    }
    return;
  }


  // 제자리 회전: rotate <각도>  (+ 오른쪽/시계, - 왼쪽/반시계)
  if (dir == "rotate") {
    int deg = arg.toInt();
    if (deg == 0) { Serial.println("DONE rotate 0"); return; }
    if (deg >  ROTATE_MAX_DEG) deg =  ROTATE_MAX_DEG;
    if (deg < -ROTATE_MAX_DEG) deg = -ROTATE_MAX_DEG;
    rotateInPlace(deg);
    Serial.println();
    Serial.print("DONE rotate ");
    Serial.println(deg);
    return;
  }


  // encdist on / off : 엔코더 거리 방식 켜기/끄기 (리셋하면 코드 기본값)
  if (dir == "encdist") {
    if (arg == "off") USE_ENC_DIST = false;
    else if (arg == "on") USE_ENC_DIST = true;
    Serial.print("ENCDIST ");
    Serial.println(USE_ENC_DIST ? "ON" : "OFF");
    return;
  }


  // debug on / debug off : 이동 중 거리 + 엔코더 출력 켜기/끄기 (리셋하면 OFF)
  if (dir == "debug") {
    bool on = (arg == "on");
    PRINT_DISTANCE = on;
    PRINT_ENCODER  = on;
    Serial.print("DEBUG ");
    Serial.println(on ? "ON" : "OFF");
    return;
  }


  if (dir == "sync") {
    if (arg == "off") syncEnabled = false;
    else if (arg == "on") syncEnabled = true;
    Serial.print("SYNC ");
    Serial.println(syncEnabled ? "ON" : "OFF");
    return;
  }


  if (dir == "sonar") {
    if (arg == "off") sonarEnabled = false;
    else if (arg == "on") sonarEnabled = true;
    Serial.print("SONAR ");
    Serial.println(sonarEnabled ? "ON" : "OFF");
    return;
  }


  // -------------------------------
  // 엔코더: enc (누적값) / enc reset (0으로)
  // -------------------------------
  if (dir == "enc") {
    if (arg == "reset") encReset();
    Serial.print("ENC");
    for (int i = 0; i < ENC_COUNT; i++) {
      Serial.print(' ');
      Serial.print(WHEEL_NAME[i]);
      Serial.print(' ');
      Serial.print((unsigned long)encCount[i]);
    }
    Serial.println();
    return;
  }


  // -------------------------------
  // 4방향 거리 한 번
  // -------------------------------
  if (dir == "dist") {
    printAllDistances();
    return;
  }


  // -------------------------------
  // 4방향 거리 연속 (센서 고정 위치 확인용)
  // -------------------------------
  if (dir == "scan") {
    for (int k = 0; k < 20; k++) {
      printAllDistances();
      unsigned long t = millis();
      while (millis() - t < 200) {
        if (pollStopDuringMove()) {
          Serial.println("DONE stop 0");
          return;
        }
      }
    }
    Serial.println("DONE scan");
    return;
  }


  // -------------------------------
  // 바퀴 하나만 테스트: fl / fr / rl / rr
  // -------------------------------
  if (dir == "fl" || dir == "fr" || dir == "rl" || dir == "rr") {

    int in1, in2;
    bool inv;
    float trim;

    if (dir == "fl")      { in1 = FL_IN1; in2 = FL_IN2; inv = FL_INV; trim = FL_TRIM; }
    else if (dir == "fr") { in1 = FR_IN1; in2 = FR_IN2; inv = FR_INV; trim = FR_TRIM; }
    else if (dir == "rl") { in1 = RL_IN1; in2 = RL_IN2; inv = RL_INV; trim = RL_TRIM; }
    else                  { in1 = RR_IN1; in2 = RR_IN2; inv = RR_INV; trim = RR_TRIM; }

    Serial.print("TEST ");
    Serial.print(dir);
    Serial.print(" (GPIO ");
    Serial.print(in1);
    Serial.print("/");
    Serial.print(in2);
    Serial.println(") forward 1s");

    digitalWrite(LED_PIN, HIGH);
    driveMotor(in1, in2, true, inv, trimmed(MOTOR_SPEED, trim));
    delay(1000);
    stopMotor();

    Serial.println("DONE test");
    return;
  }


  if (steps < 1) {
    steps = 1;
  }


  // -------------------------------
  // 이동 명령: 방향에 맞는 센서 1개 고르기
  // -------------------------------
  void (*action)() = nullptr;
  unsigned long runMs = 0;
  int sensor = -1;

  if (dir == "forward") {
    action = moveForward;  runMs = FORWARD_RUN_MS; sensor = S_FRONT;
  }
  else if (dir == "backward") {
    action = moveBackward; runMs = FORWARD_RUN_MS; sensor = S_BACK;
  }
  else if (dir == "left") {
    action = strafeLeft;   runMs = STRAFE_RUN_MS;  sensor = S_LEFT;
  }
  else if (dir == "right") {
    action = strafeRight;  runMs = STRAFE_RUN_MS;  sensor = S_RIGHT;
  }
  else {
    Serial.println("ERR unknown " + line);
    return;
  }

  if (!sonarEnabled) {
    sensor = -1;
  }


  // -------------------------------
  // steps 칸을 멈추지 않고 한 번에 이동
  // -------------------------------
  unsigned long ranMs = 0;
  float stopDist = -1;

  encReset();
  // 출발 전 점검: 가는 방향 바로 다음 칸에 장애물이 있으면 움직이지 않고 보고
  if (sensor >= 0) {
    float v[PRECHECK_SAMPLES];
    int n = 0;
    for (int k = 0; k < PRECHECK_SAMPLES; k++) {
      float d = readDistanceCm(sensor, DIST_TIMEOUT_US);
      if (d > 0) v[n++] = d;
      delay(30);
    }
    if (n > 0) {
      for (int a = 0; a < n - 1; a++)
        for (int b = a + 1; b < n; b++)
          if (v[b] < v[a]) { float t = v[a]; v[a] = v[b]; v[b] = t; }
      float pd = v[n / 2];
      if (pd <= BLOCK_DISTANCE_CM[sensor]) {
        Serial.println();
        Serial.print("OBSTACLE ");
        Serial.print(dir);
        Serial.print(" 0 0 ");
        Serial.println(pd, 1);
        return;
      }
    }
  }

  bool strafeMove = (dir == "left" || dir == "right");
  unsigned long totalMs = runMs * steps;

  gRunMs = runMs;
  gPulsesPerCell = CELL_CM * (strafeMove ? PULSES_PER_CM_STRAFE : PULSES_PER_CM_FWD);
  gStopEarly = strafeMove ? STOP_EARLY_PULSES_STRAFE : STOP_EARLY_PULSES_FWD;

  if (USE_ENC_DIST) {
    gTargetPulses = (long)(gPulsesPerCell * steps);
    totalMs = runMs * steps * 2 + 500;          // 안전용 시간 제한 (엔코더 이상 대비)
  } else {
    gTargetPulses = 0;
    unsigned long over = strafeMove ? STRAFE_OVERSHOOT_MS : FORWARD_OVERSHOOT_MS;
    if (totalMs > over + 100) totalMs -= over;
  }

  RunResult r = runTimed(action, totalMs, sensor, ranMs, stopDist);

  if (PRINT_ENCODER) {
    printEncoder(dir == "right" ? 1 : (dir == "left" ? 2 : (dir == "backward" ? 3 : 0)));
  }

  unsigned long cellsDone = ranMs / runMs;
  unsigned long msInCell  = ranMs % runMs;

  if (r == RUN_OBSTACLE) {
    // 다음 칸 중앙에 거의 도착했으면 복귀하지 않고 그 칸에 선 것으로 처리
    float remainCm = (float)(runMs - msInCell) * CELL_CM / (float)runMs;
    if (msInCell + SNAP_FORWARD_MS >= runMs && stopDist - remainCm >= SNAP_MIN_GAP_CM) {
      cellsDone += 1;
      msInCell = 0;
    }

    // 칸 중앙으로 복귀: 이번 칸에서 간 만큼 반대로 (센서 확인 없이, 감속 정지)
    if (RETURN_TO_CENTER && msInCell > RETURN_MIN_MS + RETURN_TRIM_MS) {
      void (*back)() = nullptr;
      if (dir == "forward")       back = moveBackward;
      else if (dir == "backward") back = moveForward;
      else if (dir == "left")     back = strafeRight;
      else if (dir == "right")    back = strafeLeft;

      if (back != nullptr) {
        delay(150);   // 완전히 멈춘 뒤 출발
        unsigned long retRan = 0;
        float dummy = -1;
        unsigned long retMs = msInCell - RETURN_TRIM_MS;
        if (USE_ENC_DIST) {
          gTargetPulses = (long)((float)retMs / (float)gRunMs * gPulsesPerCell);
          runTimed(back, retMs * 2 + 500, -1, retRan, dummy);
        } else {
          gTargetPulses = 0;
          runTimed(back, retMs, -1, retRan, dummy);
        }
      }
    }

    // 형식: OBSTACLE <방향> <끝낸 칸 수> <이번 칸에서 움직인 ms> <거리 cm>
    //   (출력 시점엔 이미 칸 중앙. 끝낸 칸 수 = 지금 서 있는 칸, ms/거리는 장애물 거리 계산용)
    Serial.println();
    Serial.print("OBSTACLE ");
    Serial.print(dir);
    Serial.print(' ');
    Serial.print(cellsDone);
    Serial.print(' ');
    Serial.print(msInCell);
    Serial.print(' ');
    Serial.println(stopDist, 1);
    return;
  }

  if (r == RUN_STOPPED) {
    // 이동 중 stop 받음
    // 형식: STOPPED <방향> <끝낸 칸 수> <이번 칸에서 움직인 ms>
    // 그 다음 stop 명령에 대한 답 DONE stop 0
    Serial.println();
    Serial.print("STOPPED ");
    Serial.print(dir);
    Serial.print(' ');
    Serial.print(cellsDone);
    Serial.print(' ');
    Serial.println(msInCell);
    Serial.println("DONE stop 0");
    return;
  }

  Serial.println();
  Serial.print("DONE ");
  Serial.print(dir);
  Serial.print(' ');
  Serial.println(steps);
}


// ===============================
// 지정 시간만큼 이동
// - 기다리는 동안 (1) 시리얼에 stop 이 왔는지, (2) 고른 센서 거리 를 계속 확인
// - sensor = -1 이면 거리 확인 안 함
// ===============================
RunResult runTimed(
    void (*action)(),
    unsigned long ms,
    int sensor,
    unsigned long &ranMs,
    float &stopDist
) {

  unsigned long start = millis();
  unsigned long lastCheck = 0;
  bool firstCheck = true;
  int hits = 0;

  for (int i = 0; i < 4; i++) syncAdj[i] = 0;
  syncActive = syncEnabled;
  unsigned long lastSync = 0;
  syncW = (action == strafeRight) ? SYNC_W_RIGHT
        : (action == strafeLeft)  ? SYNC_W_LEFT
        : (action == moveBackward) ? SYNC_W_BACK
        : SYNC_W_ONE;

  encReset();
  long target = gTargetPulses;
  bool encMode = (target > 0);
  gUsedEnc = encMode;

  currentAction = action;
  action();

  while (millis() - start < ms) {

    // 1) 이동 중 stop 확인
    if (pollStopDuringMove()) {
      ranMs = encMode ? pulsesToMs(encAvg()) : millis() - start;
      currentAction = nullptr;   // 급정지: 감속 없이 바로 브레이크
      stopMotor();
      delay(100);
      return RUN_STOPPED;
    }

    unsigned long el = millis() - start;

    // 1.2) 엔코더 거리 도달 확인
    if (encMode) {
      long avg = encAvg();
      if (el > 500 && avg < 20) {
        // 엔코더가 하나도 안 들어옴 -> 이번 이동은 시간 방식으로
        encMode = false;
        gUsedEnc = false;
        ms = (unsigned long)((float)target / gPulsesPerCell * (float)gRunMs);
        Serial.println();
        Serial.println("ENCDIST FALLBACK (엔코더 신호 없음 -> 시간 방식)");
      } else if (avg >= target - gStopEarly) {
        break;
      }
    }

    // 1.5) 엔코더로 4바퀴 속도 맞추기
    if (syncActive && el >= SYNC_START_MS && millis() - lastSync >= SYNC_MS) {
      lastSync = millis();

      unsigned long c[4];
      unsigned long sum = 0, mx = 0, mn = 0xFFFFFFFFUL;
      for (int i = 0; i < 4; i++) {
        c[i] = encCount[i];
        sum += c[i];
        if (c[i] > mx) mx = c[i];
        if (c[i] < mn) mn = c[i];
      }

      // 엔코더 하나가 안 들어오면(선 빠짐) 이번 이동은 보정 끔
      if (el >= 300 && mx > 40 && mn * 2 < mx) {
        syncActive = false;
        for (int i = 0; i < 4; i++) syncAdj[i] = 0;
        Serial.println();
        Serial.println("SYNC OFF (엔코더 하나가 안 들어옴 -> 이번 이동은 보정 없이)");
        currentAction();
      } else {
        syncCompute();
        currentAction();   // 보정값 반영해서 PWM 다시 걸기
      }
    }

    // 2) 가는 방향 센서 확인
    if (sensor >= 0 && (firstCheck || millis() - lastCheck >= SENSOR_INTERVAL_MS)) {

      firstCheck = false;
      lastCheck = millis();

      float d = readDistanceCm(sensor, MOVE_TIMEOUT_US);

      if (PRINT_DISTANCE) {
        Serial.print("dist ");
        Serial.print(SONAR_NAME[sensor]);
        Serial.print(' ');
        Serial.println(d, 1);
      }

       // 기준 이하가 연속 CONFIRM_COUNT 번이면 정지 (앞뒤/좌우 기준 따로)
      float stopCm = (sensor == S_LEFT || sensor == S_RIGHT) ? STOP_DISTANCE_LR_CM : STOP_DISTANCE_FB_CM;
      if (d > 0 && d <= stopCm) {
        hits++;
      } else {
        hits = 0;
      }

      if (hits >= CONFIRM_COUNT) {
        ranMs = encMode ? pulsesToMs(encAvg()) : millis() - start;
        currentAction = nullptr;   // 급정지: 감속 없이 바로 브레이크
        stopMotor();
        stopDist = d;
        delay(100);
        return RUN_OBSTACLE;
      }
    }
  }

  bool timedOut = encMode && (millis() - start >= ms);
  unsigned long atBrake[ENC_COUNT];
  for (int i = 0; i < ENC_COUNT; i++) atBrake[i] = encCount[i];
  stopMotor();
  delay(100);   // 멈춘 뒤 관성 정리
  if (PRINT_ENCODER) printTurn(atBrake, action == strafeLeft || action == strafeRight);

  if (encMode) {
    long got = encAvg();
    if (PRINT_ENCODER) {
      Serial.println();
      Serial.print("ENCAVG target ");
      Serial.print(target);
      Serial.print(" got ");
      Serial.print(got);
      Serial.print(" over ");
      Serial.println(got - target);
    }
    if (timedOut) {
      Serial.println();
      Serial.println("ENCDIST TIMEOUT (목표 펄스 못 채움 - 바퀴 막힘/엔코더 확인)");
    }
    ranMs = (unsigned long)((float)target / gPulsesPerCell * (float)gRunMs);
  } else {
    ranMs = ms;
  }
  return RUN_DONE;
}


// ===============================
// 이동 중 시리얼 확인
// - "stop" 줄이 오면 true
// - 다른 명령이면 pendingLine 에 저장해 두고 이동 끝난 뒤 처리
// ===============================
bool pollStopDuringMove() {
  while (Serial.available() > 0) {
    char c = Serial.read();

    if (c == '\n') {
      String l = moveBuf;
      moveBuf = "";
      l.trim();

      String low = l;
      low.toLowerCase();

      if (low == "stop") {
        return true;
      }
      if (l.length() > 0) {
        pendingLine = l;
      }
    }
    else if (c != '\r') {
      moveBuf += c;
      if (moveBuf.length() > 64) {
        moveBuf = "";
      }
    }
  }
  return false;
}


// ===============================
// 기본 속도 x 바퀴별 보정 (0~255)
// ===============================
int trimmed(int base, float trim) {
  int v = (int)(base * trim * speedScale * baseScale + 0.5f);
  if (v > 255) v = 255;
  if (v < 0) v = 0;
  return v;
}


// ===============================
// 개별 모터 제어
// inverted = false : forward -> PWM / LOW
// inverted = true  : forward -> LOW / PWM
// ===============================
int wheelIndexOf(int in1) {
  if (in1 == FL_IN1) return 0;
  if (in1 == FR_IN1) return 1;
  if (in1 == RL_IN1) return 2;
  if (in1 == RR_IN1) return 3;
  return -1;
}

void driveMotor(int in1, int in2, bool forward, bool inverted, int speed) {

  // 실시간 속도 맞추기 보정 더하기
  if (syncActive) {
    int w = wheelIndexOf(in1);
    if (w >= 0) {
      speed += (int)(syncAdj[w] * speedScale);
      if (speed > 255) speed = 255;
      if (speed < 0) speed = 0;
    }
  }

  motorsRunning = true;

  bool direction = forward;
  if (inverted) {
    direction = !direction;
  }

  if (direction) {
    analogWrite(in1, speed);
    digitalWrite(in2, LOW);
  } else {
    digitalWrite(in1, LOW);
    analogWrite(in2, speed);
  }
}


void stopMotorPair(int in1, int in2) {
  analogWrite(in1, 0);
  analogWrite(in2, 0);
  digitalWrite(in1, LOW);
  digitalWrite(in2, LOW);
}


// 전체 정지: 달리던 중이면 4바퀴 동시에 짧게 브레이크 -> 전원 끊기
// (그냥 끊으면 바퀴마다 관성으로 서는 시점이 달라서 마지막에 틀어짐)
void stopMotor() {
  digitalWrite(LED_PIN, LOW);

  // 1) 4바퀴 같이 감속 (급정지면 건너뜀)
  bool ramped = false;
  if (motorsRunning && currentAction != nullptr) {
    ramped = true;
    for (int k = RAMP_STEPS - 1; k >= 1; k--) {
      speedScale = (float)k / RAMP_STEPS;
      if (syncActive && SYNC_DURING_RAMP) syncCompute();   // 감속 중에도 4바퀴 펄스를 계속 맞춘다
      currentAction();
      delay(RAMP_MS / RAMP_STEPS);
    }
    speedScale = 1.0;
  }
  currentAction = nullptr;

  // 2) 짧게 브레이크
  if (motorsRunning) {
    analogWrite(FL_IN1, 255); analogWrite(FL_IN2, 255);
    analogWrite(FR_IN1, 255); analogWrite(FR_IN2, 255);
    analogWrite(RL_IN1, 255); analogWrite(RL_IN2, 255);
    analogWrite(RR_IN1, 255); analogWrite(RR_IN2, 255);
    delay(ramped ? BRAKE_MS : EMERGENCY_BRAKE_MS);
  }

  stopMotorPair(FL_IN1, FL_IN2);
  stopMotorPair(FR_IN1, FR_IN2);
  stopMotorPair(RL_IN1, RL_IN2);
  stopMotorPair(RR_IN1, RR_IN2);

  motorsRunning = false;
  syncActive = false;
}


// ===============================
// 전진 / 후진
// ===============================
void moveForward() {
  digitalWrite(LED_PIN, HIGH);
  driveMotor(FL_IN1, FL_IN2, true, FL_INV, trimmed(MOTOR_SPEED, FL_TRIM));
  driveMotor(FR_IN1, FR_IN2, true, FR_INV, trimmed(MOTOR_SPEED, FR_TRIM));
  driveMotor(RL_IN1, RL_IN2, true, RL_INV, trimmed(MOTOR_SPEED, RL_TRIM));
  driveMotor(RR_IN1, RR_IN2, true, RR_INV, trimmed(MOTOR_SPEED, RR_TRIM));
}

void moveBackward() {
  digitalWrite(LED_PIN, HIGH);
  driveMotor(FL_IN1, FL_IN2, false, FL_INV, trimmed(MOTOR_SPEED, BFL_TRIM));
  driveMotor(FR_IN1, FR_IN2, false, FR_INV, trimmed(MOTOR_SPEED, BFR_TRIM));
  driveMotor(RL_IN1, RL_IN2, false, RL_INV, trimmed(MOTOR_SPEED, BRL_TRIM));
  driveMotor(RR_IN1, RR_IN2, false, RR_INV, trimmed(MOTOR_SPEED, BRR_TRIM));
}


// ===============================
// 왼쪽 횡이동: FL 후진, FR 전진, RL 전진, RR 후진
// ===============================
void strafeLeft() {
  digitalWrite(LED_PIN, HIGH);
  driveMotor(FL_IN1, FL_IN2, false, FL_INV, trimmed(STRAFE_SPEED, LFL_TRIM));
  driveMotor(FR_IN1, FR_IN2, true,  FR_INV, trimmed(STRAFE_SPEED, LFR_TRIM));
  driveMotor(RL_IN1, RL_IN2, true,  RL_INV, trimmed(STRAFE_SPEED, LRL_TRIM));
  driveMotor(RR_IN1, RR_IN2, false, RR_INV, trimmed(STRAFE_SPEED, LRR_TRIM));
}


// ===============================
// 오른쪽 횡이동: FL 전진, FR 후진, RL 후진, RR 전진
// ===============================
void strafeRight() {
  digitalWrite(LED_PIN, HIGH);
  driveMotor(FL_IN1, FL_IN2, true,  FL_INV, trimmed(STRAFE_SPEED, SFL_TRIM));
  driveMotor(FR_IN1, FR_IN2, false, FR_INV, trimmed(STRAFE_SPEED, SFR_TRIM));
  driveMotor(RL_IN1, RL_IN2, false, RL_INV, trimmed(STRAFE_SPEED, SRL_TRIM));
  driveMotor(RR_IN1, RR_IN2, true,  RR_INV, trimmed(STRAFE_SPEED, SRR_TRIM));
}


// ===============================
// 초음파 거리 (cm). 응답이 없으면 -1
// ===============================
float readDistanceCm(int sensor, unsigned long timeoutUs) {
  int trig = TRIG_PINS[sensor];
  int echo = ECHO_PINS[sensor];

  digitalWrite(trig, LOW);
  delayMicroseconds(2);
  digitalWrite(trig, HIGH);
  delayMicroseconds(10);
  digitalWrite(trig, LOW);

  unsigned long duration = pulseIn(echo, HIGH, timeoutUs);

  if (duration == 0) {
    return -1;
  }
  return duration * 0.0343f / 2.0f;
}


// ===============================
// 4방향 거리 한 줄 출력
// 예: DIST front 52.3 left -1.0 back 120.4 right 33.1
// 센서끼리 초음파가 섞이지 않게 하나씩 30ms 간격으로 잼
// ===============================
void printAllDistances() {
  Serial.print("DIST");
  for (int i = 0; i < SONAR_COUNT; i++) {
    float d = readDistanceCm(i, DIST_TIMEOUT_US);
    Serial.print(' ');
    Serial.print(SONAR_NAME[i]);
    Serial.print(' ');
    Serial.print(d, 1);
    delay(30);
  }
  Serial.println();
}


// ===============================
// 엔코더 유틸
// ===============================
void encReset() {
  for (int i = 0; i < ENC_COUNT; i++) encCount[i] = 0;
}

// 바퀴별 펄스 + 가장 많이 돈 바퀴 대비 % + 추천 TRIM
void printEncoder(int mode) {
  unsigned long c[ENC_COUNT];
  for (int i = 0; i < ENC_COUNT; i++) c[i] = encCount[i];

  const float fwdTrims[ENC_COUNT]    = {FL_TRIM, FR_TRIM, RL_TRIM, RR_TRIM};
  const float strafeTrims[ENC_COUNT] = {SFL_TRIM, SFR_TRIM, SRL_TRIM, SRR_TRIM};
  const float leftTrims[ENC_COUNT]   = {LFL_TRIM, LFR_TRIM, LRL_TRIM, LRR_TRIM};
  const float backTrims[ENC_COUNT]   = {BFL_TRIM, BFR_TRIM, BRL_TRIM, BRR_TRIM};
  const float* trims = (mode == 1) ? strafeTrims : (mode == 2 ? leftTrims : (mode == 3 ? backTrims : fwdTrims));

  unsigned long mx = 0, mn = 0xFFFFFFFFUL;
  for (int i = 0; i < ENC_COUNT; i++) {
    if (c[i] > mx) mx = c[i];
    if (c[i] < mn) mn = c[i];
  }

  Serial.println();
  Serial.print("ENC");
  for (int i = 0; i < ENC_COUNT; i++) {
    Serial.print(' ');
    Serial.print(WHEEL_NAME[i]);
    Serial.print(' ');
    Serial.print(c[i]);
  }
  Serial.println();

  if (mx == 0 || mn == 0) {
    Serial.println("ENC WARN: 0 인 바퀴 있음 -> 그 바퀴 C1/VCC/GND 확인 (RR 이면 풀업 10k)");
    return;
  }

  Serial.print("ENC%");
  for (int i = 0; i < ENC_COUNT; i++) {
    Serial.print(' ');
    Serial.print(WHEEL_NAME[i]);
    Serial.print(' ');
    Serial.print(c[i] * 100UL / mx);
  }
  Serial.println();

  // 가장 느린 바퀴에 나머지를 맞춘 TRIM (이번 이동 기준)
  Serial.print(mode == 1 ? "SUGGEST(right)" : (mode == 2 ? "SUGGEST(left)" : (mode == 3 ? "SUGGEST(back)" : "SUGGEST")));
  for (int i = 0; i < ENC_COUNT; i++) {
    Serial.print(' ');
    if (mode == 1) Serial.print('S');
    if (mode == 2) Serial.print('L');
    if (mode == 3) Serial.print('B');
    Serial.print(WHEEL_NAME[i]);
    Serial.print("_TRIM ");
    Serial.print(trims[i] * (float)mn / (float)c[i], 2);
  }
  Serial.println();
}


// 이동 한 번에 생긴 좌우(또는 앞뒤) 바퀴 펄스 차이 -> cm, 각도 어림
void printTurn(const unsigned long *atBrake, bool strafe) {
  unsigned long c[ENC_COUNT];
  for (int i = 0; i < ENC_COUNT; i++) c[i] = encCount[i];
  if (c[0] == 0 || c[1] == 0 || c[2] == 0 || c[3] == 0) return;   // 엔코더 빠진 바퀴가 있으면 의미 없음
  float ppc = strafe ? PULSES_PER_CM_STRAFE : PULSES_PER_CM_FWD;
  float span = strafe ? WHEELBASE_CM : TRACK_CM;
  // 전진/후진: 왼쪽(FL 0, RL 2) - 오른쪽(FR 1, RR 3) / 좌우 이동: 앞(FL 0, FR 1) - 뒤(RL 2, RR 3)
  int a1 = 0, a2 = strafe ? 1 : 2, b1 = strafe ? 2 : 1, b2 = 3;
  float dBrake = ((float)atBrake[a1] + atBrake[a2] - atBrake[b1] - atBrake[b2]) / 2.0f;
  float dEnd   = ((float)c[a1] + c[a2] - c[b1] - c[b2]) / 2.0f;
  Serial.println();
  Serial.print(strafe ? "TURN F-R" : "TURN L-R");
  Serial.print(" brake "); Serial.print(dBrake, 0);
  Serial.print(" end ");   Serial.print(dEnd, 0);
  Serial.print(" pulses = "); Serial.print(dEnd / ppc, 2); Serial.print(" cm");
  if (span > 0) {
    Serial.print(" ~ ");
    Serial.print(dEnd / ppc / span * 57.2958f, 1);
    Serial.print(" deg");
  }
  Serial.println();
}


// 4바퀴 누적 펄스를 비교해서 바퀴별 PWM 보정값(syncAdj)을 계산한다 (주행 중 + 감속 중 공용)
void syncCompute() {
  unsigned long c[4];
  for (int i = 0; i < 4; i++) c[i] = encCount[i];
  float nsum = 0;
  for (int i = 0; i < 4; i++) nsum += (float)c[i] / syncW[i];
  float nmean = nsum / 4.0f;
  for (int i = 0; i < 4; i++) {
    int a = (int)(SYNC_KP * (nmean * syncW[i] - (float)c[i]));
    if (a >  SYNC_MAX_ADJ) a =  SYNC_MAX_ADJ;
    if (a < -SYNC_MAX_ADJ) a = -SYNC_MAX_ADJ;
    syncAdj[i] = a;
  }
}
