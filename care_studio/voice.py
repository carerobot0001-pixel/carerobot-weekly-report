"""음성 입력 — 브라우저 내장 음성인식(Web Speech API).

HIFA 1단계에서 '음성 기록'만 떼어낸 것. Realtime 대화·RAG·VLM은 아직 없다.
Dolbom Studio의 `voice_note.py`와 같은 방식이고, 여기서는 **말한 문장을 그대로
돌려주는 것**까지만 한다(해석은 `store.parse`가 한다).

⚠️ 음성이 브라우저 제조사(크롬=구글) 서버를 거친다. 이용자 실명이 그대로 나가면
안 되므로, 시연·시험 단계에서는 **가명이나 코드**로 부르게 안내한다.
⚠️ 크롬 계열에서만 된다(안드로이드·PC). iOS 사파리는 안 된다.
"""
import streamlit as st

try:
    from streamlit_js_eval import streamlit_js_eval
    _OK = True
except Exception:
    _OK = False

_ERR = "##ERR##"

_ENGINE = """
(function(){
  if (window.__csVoice) return "ok";
  var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) { window.__csVoice = {unsupported:true}; return "unsupported"; }
  var r = new SR();
  r.lang = "ko-KR"; r.continuous = true; r.interimResults = false;
  var s = {text:"", on:false, err:""};
  r.onresult = function(e){
    for (var i = e.resultIndex; i < e.results.length; i++) {
      if (e.results[i].isFinal) { s.text += e.results[i][0].transcript + " "; }
    }
  };
  r.onerror = function(e){ s.err = e.error || "error"; };
  r.onend = function(){ if (s.on) { try { r.start(); } catch(x) {} } };
  window.__csVoice = { s:s,
    start:function(){ s.text=""; s.err=""; s.on=true; try{r.start();}catch(x){} },
    stop: function(){ s.on=false; try{r.stop();}catch(x){} } };
  return "ok";
})()
"""

_START = """
(function(){
  if (!window.__csVoice) return "noengine";
  if (window.__csVoice.unsupported) return "unsupported";
  window.__csVoice.start(); return "started";
})()
"""

_STOP = """
(function(){
  if (!window.__csVoice || window.__csVoice.unsupported)
    return "##ERR##unsupported";
  window.__csVoice.stop();
  var s = window.__csVoice.s;
  return (s.text || "").trim() || ("##ERR##" + (s.err || "empty"));
})()
"""


def available():
    return _OK


def _seq():
    n = st.session_state.get("_cs_seq", 0) + 1
    st.session_state["_cs_seq"] = n
    return n


def listen_box(key="cs"):
    """🎤/■ 버튼. 정지하면 인식된 문장을 반환(없으면 None).

    반환된 문장은 곧바로 저장하지 않는다 — 호출한 쪽이 초안으로 보여주고
    사람이 확인한 뒤 저장한다.
    """
    if not _OK:
        st.info("음성 입력을 쓰려면 `streamlit-js-eval` 이 필요합니다.")
        return None
    on = st.session_state.get("_cs_on")
    if not on:
        if st.button("🎤 말해서 기록하기", key=f"{key}_go",
                     use_container_width=True, type="primary"):
            st.session_state["_cs_on"] = True
            st.session_state["_cs_step"] = "start"
            st.rerun()
        return None

    st.caption("🔴 듣는 중 — 예: \"김OO 님 배설 완료, 시간이 좀 걸렸어요\"  "
               "말이 끝나면 ■ 를 누르세요.")
    if st.button("■ 정지", key=f"{key}_stop", use_container_width=True):
        st.session_state["_cs_step"] = "stop"
        st.rerun()

    step = st.session_state.get("_cs_step")
    if step == "start":
        streamlit_js_eval(js_expressions=_ENGINE, key=f"cs_init_{_seq()}")
        streamlit_js_eval(js_expressions=_START, key=f"cs_start_{_seq()}")
        st.session_state["_cs_step"] = "listening"
    elif step == "stop":
        got = streamlit_js_eval(js_expressions=_STOP, key=f"cs_stop_{_seq()}")
        if got is None:
            return None
        st.session_state["_cs_on"] = False
        st.session_state["_cs_step"] = None
        if isinstance(got, str) and got.startswith(_ERR):
            why = got[len(_ERR):]
            msg = {"unsupported": "이 브라우저는 음성인식을 지원하지 않습니다. "
                                  "안드로이드·PC 크롬에서 사용해 주세요.",
                   "not-allowed": "마이크 권한이 거부됐습니다.",
                   "empty": "들린 말이 없습니다. 다시 시도해 주세요."}
            st.warning(msg.get(why, f"음성인식 오류: {why}"))
            st.rerun()
        return (got or "").strip() or None
    return None
