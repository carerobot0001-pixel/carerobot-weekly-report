const pptxgen = require("pptxgenjs");
const fs = require("fs");
const path = require("path");

const REPO = "C:/Users/carer/Desktop/돌봄로봇_업무보고_김건양";
const SHOTS = path.join(REPO, "docs", "screenshots");
const OUT = path.join(REPO, "docs", "dolbom_studio_소개.pptx");

// ---- palette (dolbom / warm terracotta-orange-brown) ----
const ESPRESSO = "3E2A1C", ORANGE = "C4622D", ORANGE_L = "E08A3C",
      BROWN = "5A3A24", SAND = "F7F0E8", SAND2 = "F1E4D3", CREAM = "F4EBE1",
      INK = "33291F", MUTED = "8A7A6B", WHITE = "FFFFFF", LINE = "E4D5C4";
const F = "Malgun Gothic";
const W = 13.3, H = 7.5, M = 0.7;

const pres = new pptxgen();
pres.defineLayout({ name: "W", width: W, height: H });
pres.layout = "W";
pres.author = "dolbom studio";
pres.title = "dolbom studio — 만들어온 과정";

const shadow = () => ({ type: "outer", color: "000000", blur: 7, offset: 3, angle: 90, opacity: 0.12 });

function titleBar(s, kicker, title, color = ORANGE) {
  s.addText(kicker, { x: M, y: 0.5, w: W - 2 * M, h: 0.3, fontFace: F, fontSize: 12, color: MUTED, bold: true, charSpacing: 2, margin: 0 });
  s.addText(title, { x: M, y: 0.78, w: W - 2 * M, h: 0.7, fontFace: F, fontSize: 30, color, bold: true, margin: 0 });
}

// screenshot box: embed if file exists, else labeled placeholder
function shot(s, file, x, y, w, h, caption) {
  const p = path.join(SHOTS, file);
  if (fs.existsSync(p)) {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: WHITE }, line: { color: LINE, width: 1 }, rectRadius: 0.08, shadow: shadow() });
    s.addImage({ path: p, x: x + 0.12, y: y + 0.12, w: w - 0.24, h: h - 0.24, sizing: { type: "contain", w: w - 0.24, h: h - 0.24 } });
  } else {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: SAND2 }, line: { color: ORANGE_L, width: 1.25, dashType: "dash" }, rectRadius: 0.08 });
    s.addText([
      { text: "📷  스크린샷 자리\n", options: { fontSize: 15, bold: true, color: BROWN, breakLine: true } },
      { text: caption + "\n\n", options: { fontSize: 12, color: BROWN, breakLine: true } },
      { text: `docs/screenshots/${file} 저장 시 자동 삽입`, options: { fontSize: 9.5, color: MUTED, italic: true } },
    ], { x: x + 0.2, y, w: w - 0.4, h, align: "center", valign: "middle", fontFace: F });
  }
}

// -------- Slide 1: Title (espresso) --------
let s = pres.addSlide();
s.background = { color: ESPRESSO };
s.addText("돌봄로봇중개연구사업단", { x: M, y: 1.0, w: 8, h: 0.4, fontFace: F, fontSize: 14, color: ORANGE_L, bold: true, charSpacing: 3, margin: 0 });
s.addText([
  { text: "dolbom ", options: { color: CREAM } },
  { text: "studio", options: { color: ORANGE_L } },
], { x: M, y: 2.1, w: 11, h: 1.4, fontFace: F, fontSize: 66, bold: true, margin: 0 });
s.addText("돌봄로봇 사업단 주간 업무 · 협업 웹앱", { x: M, y: 3.65, w: 11, h: 0.5, fontFace: F, fontSize: 22, color: CREAM, margin: 0 });
s.addText("왜 시작했고, 어떻게 계속 바꿔왔는가 — 만들어온 과정", { x: M, y: 4.25, w: 11, h: 0.45, fontFace: F, fontSize: 15, color: ORANGE_L, italic: true, margin: 0 });
// motif: bara tiles row
const tiles = ["📌", "📝", "🛒", "📋", "📍", "🔧"];
tiles.forEach((t, i) => {
  const tx = M + i * 1.0;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: tx, y: 5.55, w: 0.8, h: 0.8, fill: { color: "4A3423" }, line: { color: ORANGE, width: 1 }, rectRadius: 0.12 });
  s.addText(t, { x: tx, y: 5.55, w: 0.8, h: 0.8, align: "center", valign: "middle", fontSize: 20, fontFace: F });
});
s.addText("2026.04 → 2026.07", { x: W - 3.2, y: 6.9, w: 2.5, h: 0.3, align: "right", fontFace: F, fontSize: 11, color: MUTED, margin: 0 });
s.addNotes("dolbom studio 소개. 돌봄로봇 사업단의 주간 업무·협업을 하나로 모은 웹앱을 왜 만들었고 어떻게 계속 개선해왔는지 보여주는 발표.");

// -------- Slide 2: Why (problem) --------
s = pres.addSlide();
s.background = { color: WHITE };
titleBar(s, "WHY", "왜 시작했나 — 매주 반복되는 수작업");
s.addText("10명이 각자 만들고, 한 명이 손으로 취합하고, 나머지 관리 업무는 엑셀·한글·카톡에 흩어져 있었다.",
  { x: M, y: 1.55, w: W - 2 * M, h: 0.4, fontFace: F, fontSize: 14, color: INK, margin: 0 });
const pains = [
  ["주간 업무보고", "각자 작성 → 한 명이 복붙 취합(주당 30~60분), 서식 깨짐, 미제출 파악 수동"],
  ["공통확인사항", "최혜민 연구원이 매주 한글 표를 처음부터 다시 제작"],
  ["구매요청", "엑셀 양식 제각각 · 배포·수합 번거로움"],
  ["장비 사용현황", "연구별 시트를 수식으로 분류 · 동기화 부담"],
  ["문제 접수 · FAQ", "카톡·구두로만 · 기록과 미해결 추적 안 됨"],
  ["공지 · 일정", "카톡에 흘러가 놓치기 쉬움"],
];
pains.forEach((p, i) => {
  const col = i % 2, row = Math.floor(i / 2);
  const x = M + col * 6.05, y = 2.15 + row * 1.62, w = 5.75, h = 1.42;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: SAND }, line: { color: LINE, width: 1 }, rectRadius: 0.09, shadow: shadow() });
  s.addShape(pres.shapes.OVAL, { x: x + 0.28, y: y + 0.28, w: 0.62, h: 0.62, fill: { color: ORANGE } });
  s.addText(String(i + 1), { x: x + 0.28, y: y + 0.28, w: 0.62, h: 0.62, align: "center", valign: "middle", fontFace: F, fontSize: 20, bold: true, color: WHITE, margin: 0 });
  s.addText(p[0], { x: x + 1.1, y: y + 0.2, w: w - 1.3, h: 0.4, fontFace: F, fontSize: 16, bold: true, color: BROWN, margin: 0 });
  s.addText(p[1], { x: x + 1.1, y: y + 0.6, w: w - 1.3, h: 0.7, fontFace: F, fontSize: 12, color: INK, margin: 0, valign: "top" });
});
s.addNotes("기존 방식의 페인포인트. 특히 주간보고 취합이 가장 큰 수작업이었다.");

// -------- Slide 3: What (overview + architecture) --------
s = pres.addSlide();
s.background = { color: WHITE };
titleBar(s, "WHAT", "무엇을 만들었나 — 웹앱 하나로");
// left: principles
s.addText("입력은 각자, 취합·공유는 자동. 별도 서버·DB·설치 없이 URL과 비밀번호만으로.",
  { x: M, y: 1.7, w: 5.6, h: 0.9, fontFace: F, fontSize: 15, color: INK, margin: 0, valign: "top" });
[
  "취합 자동화 우선 — 사람이 하던 복붙을 없앤다",
  "결과물은 기존 한글 양식 그대로",
  "한 화면에서 공지·할 일·일정 파악",
  "담당자 없이 전원 동등하게 사용",
  "데이터가 날아가지 않게 다층 백업",
].forEach((t, i) => {
  s.addShape(pres.shapes.OVAL, { x: M, y: 2.75 + i * 0.72, w: 0.16, h: 0.16, fill: { color: ORANGE } });
  s.addText(t, { x: M + 0.32, y: 2.62 + i * 0.72, w: 5.3, h: 0.45, fontFace: F, fontSize: 13.5, color: INK, margin: 0, valign: "middle" });
});
// right: vertical flow diagram
const fx = 7.5, fw = 5.0;
const boxes = [
  ["팀원 10명", "웹 브라우저에서 각자 입력", SAND, BROWN],
  ["Streamlit 앱 (웹)", "입력 · 취합 · 자동화 · 공유", ORANGE, WHITE],
  ["Google Sheets · Calendar · Drive · News · HWPX", "저장 · 일정 · 협업파일 · 뉴스 · 취합본", SAND, BROWN],
];
boxes.forEach((b, i) => {
  const y = 1.75 + i * 1.75, h = 1.25;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: fx, y, w: fw, h, fill: { color: b[2] }, line: { color: i === 1 ? ORANGE : LINE, width: i === 1 ? 0 : 1 }, rectRadius: 0.1, shadow: shadow() });
  s.addText(b[0], { x: fx + 0.25, y: y + 0.2, w: fw - 0.5, h: 0.55, fontFace: F, fontSize: i === 1 ? 17 : 15, bold: true, color: b[3], margin: 0, valign: "middle" });
  s.addText(b[1], { x: fx + 0.25, y: y + 0.72, w: fw - 0.5, h: 0.4, fontFace: F, fontSize: 11.5, color: i === 1 ? CREAM : MUTED, margin: 0 });
  if (i < 2) s.addText("▼", { x: fx + fw / 2 - 0.3, y: y + h + 0.03, w: 0.6, h: 0.45, align: "center", fontFace: F, fontSize: 16, color: ORANGE_L, margin: 0 });
});
s.addText("비용 0원 · main 브랜치 push → 1~2분 자동 재배포", { x: fx, y: 7.02, w: fw, h: 0.35, fontFace: F, fontSize: 11, italic: true, color: MUTED, align: "center", margin: 0 });
s.addNotes("Streamlit 단일 파이썬 앱 + 구글 시트 저장. 무료, 운영 부담 최소.");

// -------- Slide 4: Impact (stats) --------
s = pres.addSlide();
s.background = { color: WHITE };
titleBar(s, "IMPACT", "얼마나 간소해졌나");
const stats = [
  ["30~60분 → 클릭 1회", "매주 취합 수작업 → 버튼 한 번에 HWPX 생성"],
  ["0원", "무료 호스팅 · 무료 구글 API · 별도 설치 없음"],
  ["업무 8종 → 앱 1개", "보고·취합·구매·장비·방문·협업·공지·일정 통합"],
  ["이름 1회 입력", "'나는 누구' 한 번 선택 → 모든 폼 자동"],
];
stats.forEach((st, i) => {
  const col = i % 2, row = Math.floor(i / 2);
  const x = M + col * 6.05, y = 1.9 + row * 2.0, w = 5.75, h = 1.75;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: i === 0 ? ORANGE : SAND }, line: { color: i === 0 ? ORANGE : LINE, width: i === 0 ? 0 : 1 }, rectRadius: 0.1, shadow: shadow() });
  s.addText(st[0], { x: x + 0.35, y: y + 0.28, w: w - 0.7, h: 0.8, fontFace: F, fontSize: 30, bold: true, color: i === 0 ? WHITE : ORANGE, margin: 0, valign: "middle" });
  s.addText(st[1], { x: x + 0.35, y: y + 1.05, w: w - 0.7, h: 0.55, fontFace: F, fontSize: 13, color: i === 0 ? CREAM : INK, margin: 0, valign: "top" });
});
s.addText("그 외 — 미제출 자동 표시 · 미제출 필드 지난주 값 자동 채움 · 화요일 17시 마감 카운트다운 · 문제/협업 추적 · 담당자 없이 전원 사용",
  { x: M, y: 6.35, w: W - 2 * M, h: 0.7, fontFace: F, fontSize: 12.5, color: MUTED, align: "center", valign: "middle", margin: 0 });
s.addNotes("가장 큰 효과는 취합 자동화. 매주 반복되던 30~60분 복붙이 버튼 한 번으로.");

// -------- Slide 5: Evolution intro (espresso timeline) --------
s = pres.addSlide();
s.background = { color: ESPRESSO };
s.addText("HOW IT EVOLVED", { x: M, y: 0.6, w: 10, h: 0.3, fontFace: F, fontSize: 12, color: ORANGE_L, bold: true, charSpacing: 2, margin: 0 });
s.addText("계속 바꿔왔다 — UI 변천사", { x: M, y: 0.9, w: 11.5, h: 0.7, fontFace: F, fontSize: 30, bold: true, color: CREAM, margin: 0 });
s.addText("\"처음엔 이랬는데 → 이렇게 → 또 이렇게 …\"  총 100여 커밋의 흐름", { x: M, y: 1.62, w: 11.5, h: 0.4, fontFace: F, fontSize: 14, italic: true, color: ORANGE_L, margin: 0 });
const stages = [
  ["1", "취합 MVP", "04월"], ["2", "기능 확장", "06월"], ["3", "홈 대시보드", "07.06"],
  ["4", "레일·바로가기", "07.07"], ["5", "담당자 제거", "07.07"], ["6", "홈 재배치", "07.09"], ["7", "브랜딩", "07.09"],
];
const n = stages.length, tw = (W - 2 * M) / n;
// timeline axis
s.addShape(pres.shapes.LINE, { x: M + tw / 2, y: 3.5, w: (W - 2 * M) - tw, h: 0, line: { color: "6B4A30", width: 2 } });
stages.forEach((st, i) => {
  const cx = M + tw * i + tw / 2;
  s.addShape(pres.shapes.OVAL, { x: cx - 0.32, y: 3.18, w: 0.64, h: 0.64, fill: { color: ORANGE }, line: { color: CREAM, width: 1.5 } });
  s.addText(st[0], { x: cx - 0.32, y: 3.18, w: 0.64, h: 0.64, align: "center", valign: "middle", fontFace: F, fontSize: 18, bold: true, color: WHITE, margin: 0 });
  s.addText(st[1], { x: cx - tw / 2 + 0.1, y: 4.0, w: tw - 0.2, h: 0.7, align: "center", fontFace: F, fontSize: 12.5, bold: true, color: CREAM, margin: 0, valign: "top" });
  s.addText(st[2], { x: cx - tw / 2 + 0.1, y: 2.7, w: tw - 0.2, h: 0.35, align: "center", fontFace: F, fontSize: 11, color: ORANGE_L, margin: 0 });
});
s.addText("→ 뒤 슬라이드에서 단계별로 화면 변화를 봅니다", { x: M, y: 6.5, w: 11, h: 0.4, fontFace: F, fontSize: 13, color: MUTED, italic: true, margin: 0 });
s.addNotes("7단계로 압축한 변천사. 다음 슬라이드부터 각 단계의 화면과 이유.");

// -------- Slides 6-12: stages --------
const stageDetail = [
  { n: 1, date: "2026.04", title: "취합 MVP — 자동화가 핵심", file: "stage1.png",
    cap: "초기: 업무보고 작성 폼 + HWPX 취합본 생성",
    what: ["팀원이 웹 폼에 줄글 입력 → 버튼 한 번에 한글(HWPX) 취합본 자동 생성",
           "미제출 필드는 지난주 값 자동 채움", "과거 회의록 열람 추가"],
    why: "가장 큰 페인포인트인 '복붙 취합'부터 없앴다. (HWPX가 한글에서 안 열리는 사태를 이분탐색으로 디버깅)" },
  { n: 2, date: "2026.06", title: "기능 확장 — 흩어진 업무 흡수", file: "stage2.png",
    cap: "구매요청·장비·방문·문서협업·스페이스·공통확인 페이지",
    what: ["구매요청서 · 장비 사용현황 · 실증 방문일지 · 문서 협업(OAuth 자동변환)",
           "스마트돌봄스페이스(FAQ·관리대장) · 사업단 공통확인사항",
           "기능 1개 = 페이지 함수 + *_store 모듈 패턴 반복"],
    why: "엑셀·카톡에 흩어져 있던 관리 업무를 하나씩 앱으로 흡수." },
  { n: 3, date: "2026.07.06", title: "홈 대시보드 도입", file: "stage3.png",
    cap: "큰 월간 달력 · 지표 · 뉴스 · 공지 · 빠른실행 버튼",
    what: ["구글 캘린더 임베드 · 관련 뉴스 · 팀 공지 · 마감 카운트다운 · 내 할 일",
           "여러 페이지를 한 화면에서 파악하도록 홈 신설"],
    why: "메뉴가 8개로 늘어 '오늘 뭘 해야 하는지' 한눈에 볼 진입점이 필요했다." },
  { n: 4, date: "2026.07.07", title: "콤팩트 · 오른쪽 레일 · 네이버식 바로가기", file: "stage4.png",
    cap: "2단 → 오른쪽 레일, 아이콘 타일 바, 뉴스 섹션 탭",
    what: ["큰 달력·긴 목록을 콤팩트하게, 오른쪽은 일정·뉴스만",
           "바로가기를 네이버 아이콘식 타일 바로", "공지 자동삭제 · 문서협업 자동공지"],
    why: "홈이 너무 길어 뉴스까지 스크롤이 멀었다. 밀도를 높이고 우선순위를 정리." },
  { n: 5, date: "2026.07.07", title: "담당자 제거 · '나는 누구' 1회", file: "stage5.png",
    cap: "단일 비밀번호로 통합 + 이름 1회 설정",
    what: ["담당자/팀원 구분·is_admin 제거 → 단일 비밀번호, 전원 동등",
           "담당자 대시보드 기능을 탭·토글로 분산",
           "접속 후 이름 1회 선택 → 세션+URL 유지 → 모든 폼 자동"],
    why: "'담당자가 따로 없다'는 현실 반영 + 매번 이름 고르는 번거로움 제거." },
  { n: 6, date: "2026.07.09", title: "홈 재배치 · 다듬기", file: "stage6.png",
    cap: "공지·오늘 챙길 것·내 할 일을 위로, 바로가기 축소",
    what: ["개인 정보(공지·할 일·내 일정)를 달력 위로 끌어올림",
           "바로가기는 작게, '나는 누구' 옆으로 · 토글 재배치(공지/일정/백업)",
           "오늘 챙길 것은 마감 임박(2일 이내)만 노출"],
    why: "가장 자주 보는 것을 맨 위로. 스크린샷 피드백을 받아 반복 미세조정." },
  { n: 7, date: "2026.07.09", title: "dolbom studio 브랜딩", file: "stage7.png",
    cap: "이름·주황/갈색 테마·네이버식 아이콘",
    what: ["사이트 이름 dolbom studio (탭·로그인·사이드바)",
           "주황/갈색 테마(primaryColor) · 바로가기 아이콘 크게·박스 없이",
           "공지등록을 바로가기 첫 타일로"],
    why: "정체성과 색을 입혀 '우리 도구'다운 느낌으로 마무리." },
];
stageDetail.forEach((d) => {
  s = pres.addSlide();
  s.background = { color: WHITE };
  // badge + title
  s.addShape(pres.shapes.OVAL, { x: M, y: 0.62, w: 0.72, h: 0.72, fill: { color: ORANGE } });
  s.addText(String(d.n), { x: M, y: 0.62, w: 0.72, h: 0.72, align: "center", valign: "middle", fontFace: F, fontSize: 26, bold: true, color: WHITE, margin: 0 });
  s.addText(`STAGE ${d.n} · ${d.date}`, { x: M + 0.95, y: 0.58, w: 8, h: 0.3, fontFace: F, fontSize: 11.5, bold: true, color: MUTED, charSpacing: 1, margin: 0 });
  s.addText(d.title, { x: M + 0.95, y: 0.86, w: 11.4 - 0.95, h: 0.6, fontFace: F, fontSize: 25, bold: true, color: BROWN, margin: 0 });
  // left text
  const lx = M, lw = 5.1;
  s.addText("무엇을 바꿨나", { x: lx, y: 1.85, w: lw, h: 0.35, fontFace: F, fontSize: 14, bold: true, color: ORANGE, margin: 0 });
  s.addText(d.what.map((t, i) => ({ text: t, options: { bullet: { indent: 14 }, breakLine: true, paraSpaceAfter: 6 } })),
    { x: lx, y: 2.25, w: lw, h: 2.6, fontFace: F, fontSize: 13, color: INK, valign: "top" });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: lx, y: 5.15, w: lw, h: 1.75, fill: { color: SAND }, line: { color: LINE, width: 1 }, rectRadius: 0.09 });
  s.addText("왜", { x: lx + 0.25, y: 5.3, w: lw - 0.5, h: 0.35, fontFace: F, fontSize: 13, bold: true, color: ORANGE, margin: 0 });
  s.addText(d.why, { x: lx + 0.25, y: 5.65, w: lw - 0.5, h: 1.15, fontFace: F, fontSize: 12.5, color: INK, margin: 0, valign: "top" });
  // right screenshot
  shot(s, d.file, 6.3, 1.85, 6.3, 5.05, d.cap);
  s.addNotes(`${d.title} — ${d.why}`);
});

// -------- Slide 13: closing (espresso) --------
s = pres.addSlide();
s.background = { color: ESPRESSO };
s.addText("정리하면", { x: M, y: 0.8, w: 11, h: 0.7, fontFace: F, fontSize: 30, bold: true, color: CREAM, margin: 0 });
s.addText("작은 자동화 하나에서 시작해, 쓰면서 계속 바꿔 온 '우리 팀 도구'", { x: M, y: 1.55, w: 11.5, h: 0.4, fontFace: F, fontSize: 14, italic: true, color: ORANGE_L, margin: 0 });
// two cards
const c1x = M, c2x = 6.95, cw = 5.35, cy = 2.4, ch = 3.4;
[["효과", ORANGE, [
  "매주 취합 30~60분 → 클릭 1회",
  "8종 업무를 앱 하나로",
  "이름 1회 → 전 페이지 자동",
  "담당자 없이 전원 사용 · 운영비 0원",
  "다층 백업으로 데이터 안전",
]], ["앞으로", BROWN, [
  "streamlit_app.py 페이지 파일 분리",
  "공통확인 표를 메인 취합본에 통합",
  "통일된 주황/갈색 아이콘 세트(SVG)",
  "캘린더 권한 대비 읽기 목록 폴백",
]]].forEach((c, i) => {
  const x = i === 0 ? c1x : c2x;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: cy, w: cw, h: ch, fill: { color: "4A3423" }, line: { color: c[1], width: 1.25 }, rectRadius: 0.1 });
  s.addText(c[0], { x: x + 0.35, y: cy + 0.25, w: cw - 0.7, h: 0.45, fontFace: F, fontSize: 18, bold: true, color: c[1] === ORANGE ? ORANGE_L : CREAM, margin: 0 });
  s.addText(c[2].map((t) => ({ text: t, options: { bullet: { indent: 14 }, breakLine: true, paraSpaceAfter: 8, color: CREAM } })),
    { x: x + 0.35, y: cy + 0.85, w: cw - 0.7, h: ch - 1.1, fontFace: F, fontSize: 13, valign: "top" });
});
s.addText([
  { text: "carerobot-weekly-report.streamlit.app", options: { color: ORANGE_L, bold: true } },
  { text: "   ·   비밀번호 carerobot (전원 공용)", options: { color: MUTED } },
], { x: M, y: 6.2, w: 11.5, h: 0.4, fontFace: F, fontSize: 14, margin: 0 });
s.addText("dolbom studio", { x: M, y: 6.75, w: 6, h: 0.4, fontFace: F, fontSize: 13, bold: true, color: CREAM, margin: 0 });
s.addNotes("마무리: 효과 요약과 향후 과제. 계속 개선 중.");

pres.writeFile({ fileName: OUT }).then((f) => console.log("WROTE", f));
