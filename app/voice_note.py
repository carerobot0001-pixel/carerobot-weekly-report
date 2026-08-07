"""음성으로 입력칸 채우기 — 현장에서 손을 못 쓸 때.

실증 현장에서 헤드셋(BONX Grip 등 아무 블루투스 이어셋)을 한쪽 귀에 꽂고 말하면
그 내용이 양식 칸에 들어간다. 돌아와서 기억으로 쓰던 것을 현장에서 끝낸다.

**어떻게 동작하나**
브라우저 내장 음성인식(Web Speech API)을 쓴다. 설치할 것도, 낼 돈도 없다.
`streamlit_js_eval`로 앱이 떠 있는 창(부모 프레임)에 인식기를 하나 만들어 두고,
🎤(시작) → ■(정지) 두 번의 리런으로 결과를 받아온다.

⚠️ **음성이 브라우저 제조사(크롬=구글) 서버를 거친다.** 그래서 화면에
참여자는 **이름 대신 코드**로 말하라고 안내한다. 완전히 로컬로 해야 하는
기록은 이 기능을 쓰지 말고 녹음 후 PC에서 변환할 것.

⚠️ **크롬 계열에서만 된다.** iOS 사파리는 지원이 없거나 불안정하다.
안 되는 브라우저에서는 버튼이 뜨되 눌렀을 때 안내가 나온다.

⚠️ 위젯 키에 직접 쓰면 Streamlit이 막는다(이미 만들어진 위젯은 못 고침).
그래서 `<key>_buf`에 넣어두고, **다음 실행에서 위젯이 만들어지기 전에**
`apply_buffer()`가 옮긴다. 폼을 그리기 맨 앞에서 불러야 한다.
"""
import streamlit as st

try:
    from streamlit_js_eval import streamlit_js_eval
    _JS_OK = True
except Exception:                                   # 라이브러리 없으면 조용히 꺼짐
    _JS_OK = False

_ERR = "##ERR##"          # 결과 대신 오류를 돌려줄 때 붙이는 표식

# 부모 창에 인식기를 한 번만 만들어 둔다. 리런이 나도 창은 그대로라 살아 있다.
_ENGINE_JS = """
(function(){
  if (window.__dsVoice) return "ok";
  var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) { window.__dsVoice = {unsupported:true}; return "unsupported"; }
  var r = new SR();
  r.lang = "ko-KR"; r.continuous = true; r.interimResults = false;
  var s = {text:"", on:false, err:""};
  r.onresult = function(e){
    for (var i = e.resultIndex; i < e.results.length; i++) {
      if (e.results[i].isFinal) { s.text += e.results[i][0].transcript + " "; }
    }
  };
  r.onerror = function(e){ s.err = e.error || "error"; };
  /* 말이 끊기면 브라우저가 멋대로 멈춘다 → 정지를 누르기 전까진 다시 켠다 */
  r.onend = function(){ if (s.on) { try { r.start(); } catch(x) {} } };
  window.__dsVoice = {
    s: s,
    start: function(){ s.text=""; s.err=""; s.on=true;
                       try { r.start(); } catch(x) {} },
    stop:  function(){ s.on=false; try { r.stop(); } catch(x) {} }
  };
  return "ok";
})()
"""

_START_JS = """
(function(){
  if (!window.__dsVoice) return "noengine";
  if (window.__dsVoice.unsupported) return "unsupported";
  window.__dsVoice.start(); return "started";
})()
"""

_STOP_JS = """
(function(){
  if (!window.__dsVoice || window.__dsVoice.unsupported)
    return "##ERR##unsupported";
  window.__dsVoice.stop();
  var s = window.__dsVoice.s;
  return (s.text || "").trim() || ("##ERR##" + (s.err || "empty"));
})()
"""


def available():
    return _JS_OK


def _seq():
    """streamlit_js_eval은 key마다 한 번만 돈다 → 누를 때마다 새 key를 준다."""
    n = st.session_state.get("_voice_seq", 0) + 1
    st.session_state["_voice_seq"] = n
    return n


def apply_buffer(*state_keys):
    """받아 적은 결과를 위젯 키로 옮긴다. **위젯을 만들기 전에** 부를 것."""
    for k in state_keys:
        buf = st.session_state.pop(f"{k}_buf", None)
        if buf is not None:
            st.session_state[k] = buf


def mic(state_key, label="음성으로 입력", append=True):
    """🎤/■ 버튼 한 쌍. 정지하면 인식 결과를 `<state_key>_buf`에 넣고 리런한다.

    append=True 면 그 칸에 이미 있던 내용 뒤에 이어 붙인다(여러 번 나눠 말하기).
    """
    if not _JS_OK:
        return
    listening = st.session_state.get("_voice_on") == state_key
    if not listening:
        if st.button(f"🎤 {label}", key=f"voice_go_{state_key}",
                     use_container_width=True):
            st.session_state["_voice_on"] = state_key
            st.session_state["_voice_step"] = "start"
            st.rerun()
        return

    st.caption("🔴 듣는 중 — 말이 끝나면 ■ 를 누르세요. "
               "참여자는 **이름 대신 코드**로 말해 주세요.")
    if st.button("■ 정지하고 담기", key=f"voice_stop_{state_key}",
                 type="primary", use_container_width=True):
        st.session_state["_voice_step"] = "stop"
        st.rerun()

    step = st.session_state.get("_voice_step")
    if step == "start":
        streamlit_js_eval(js_expressions=_ENGINE_JS, key=f"vinit_{_seq()}")
        streamlit_js_eval(js_expressions=_START_JS, key=f"vstart_{_seq()}")
        st.session_state["_voice_step"] = "listening"
    elif step == "stop":
        got = streamlit_js_eval(js_expressions=_STOP_JS, key=f"vstop_{_seq()}")
        if got is None:                       # 아직 브라우저 응답 전 — 다음 실행에
            return
        st.session_state["_voice_on"] = None
        st.session_state["_voice_step"] = None
        if isinstance(got, str) and got.startswith(_ERR):
            why = got[len(_ERR):]
            if why == "unsupported":
                st.warning("이 브라우저는 음성인식을 지원하지 않습니다. "
                           "안드로이드/PC 크롬에서 사용해 주세요.")
            elif why == "not-allowed":
                st.warning("마이크 권한이 거부됐습니다. 주소창 왼쪽 자물쇠에서 "
                           "마이크를 허용해 주세요.")
            elif why == "empty":
                st.info("들린 말이 없습니다. 다시 시도해 주세요.")
            else:
                st.warning(f"음성인식 오류: {why}")
            st.rerun()
        text = (got or "").strip()
        if text:
            old = (st.session_state.get(state_key, "") or "").strip()
            st.session_state[f"{state_key}_buf"] = (
                (old + "\n" + text).strip() if (append and old) else text)
        st.rerun()
