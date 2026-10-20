"""구어체 인용 검사 (D-0438).

**이 시험이 지키는 것은 둘이다.** 그물이 비지 않았다는 것과, 자료인 발화는 안
건드린다는 것이다. 앞은 D-0230이 시킨 것이고 뒤는 이 규칙이 **측정을 지우지 않게**
하는 선이다.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.conftest import tool_module

if TYPE_CHECKING:
    from types import ModuleType

SPEECH = tool_module("doc_speech")
STYLE = tool_module("check_doc_style")
ALLOW = STYLE.ALLOW
ROOT = Path(STYLE.ROOT)


def _said(body: str, marker: str = "") -> list[tuple[int, str]]:
    """규칙 10의 표지는 **규칙 4와 다르다** (D-0443)."""
    found: list[tuple[int, str]] = SPEECH.speech(body, marker or SPEECH.SPEECH_OK)
    return found


# ------------------------------------------------------------------ 잡는다


@pytest.mark.parametrize(
    "quoted",
    [
        "아니 왜 두 벌이 되는 거야? 기존 걸 날리면 되지 않냐.",
        "문서 체계 더 늘리기 싫어. 조만간 병합할 거야.",
        "아니 왜 안막지?? 파이어레인이라도 참고할래? verify의 전문가인데;;",
        "빚 상환은 건수가 중요하지 라인 수가 중요한 게 아니지 않나",
        "돌리는 속도가 너무 오래 걸리는 느낌인데 이거 맞아?",
        "문서 4축은 디시즌 마스터 플랜 프로포절인데? 흡수 가능하잖아.",
        "이거 왜 하는지 모르겠다. 그냥 넘겨도 되냐?",
    ],
)
def test_구어체_인용을_잡는다(quoted: str) -> None:
    """다섯 갈래를 **한 갈래씩** 민다. 한 갈래가 죽어도 나머지가 가려 주면 못 본다."""
    assert _said(f'- **배경**: 사용자가 말했다 — *"{quoted}"*\n'), f"못 잡았다: {quoted}"


def test_줄을_넘는_인용도_잡는다() -> None:
    """**인용 덩어리가 단위다** — 실측 53건 중 14건이 두 줄 이상이었다.

    줄 단위로 보면 뒷줄에만 구어가 있는 인용을 통째로 놓친다.
    """
    assert _said('- **배경**: 사용자가 물었다 — *"앞줄은 멀쩡하다.\n  뒷줄에 가서 이거 맞아?"*\n')


# ------------------------------------------------------------------ 안 잡는다


@pytest.mark.parametrize(
    "line",
    [
        '- **배경**: 기록이 *"지표가 목표가 된다"*고 적었다.',
        "- **배경**: 화면이 *«PLAN 열린 질문 29»*를 찍었다.",
        '- **배경**: *"Environment URL is not a valid http(s) URL"*로 죽었다.',
        "- **배경**: 그가 물었다 — 왜 두 벌이 되는가, 기존 것을 없애면 되지 않는가.",
        "- **배경**: *«추가 수집은 하지 않는다»*는 조건이 달려 있었다.",
        "- **배경**: *«붙여 놓으면 아무것도 못 잡는 하네스»*가 D-0353의 이름이다.",
    ],
)
def test_구어가_아니면_안_잡는다(line: str) -> None:
    """**경보가 반이 거짓이면 끈다** (GR-0.8).

    기록 인용·화면 문구·오류 메시지·평어체 간접 서술·개념 이름은 전부 정상이다.
    `하네스`가 `하네`에, `하지 않는다`가 `하지?`에 걸렸던 자리를 그대로 둔다.
    """
    assert not _said(line + "\n"), f"오탐: {line}"


def test_자료인_발화는_표지로_남는다() -> None:
    """**발화가 측정값인 자리가 있다.**

    사용자가 친 주문 한 줄이 D-0422의 자료다 — 간접 서술로 옮기면 **그가 무엇을
    입력했는지가 사라진다.** 표지를 단 자리는 안 본다.
    """
    typed = "> *«바다가자, You(=i), 처음부터 너와 나 좋아하는데 이런 노래 만들어줘»*"
    assert _said(typed + "\n")
    assert not _said(f"{typed}  {SPEECH.SPEECH_OK}\n")


def test_귀_판정_대부분은_그물_밖이다() -> None:
    """**이 관문은 재현율이 낮다. 알고 그렇게 뒀다** (GR-0.8).

    귀 판정 여섯 중 다섯은 걸릴 낱말이 없어 안 잡힌다 — *«왠지 모르겠는데 별로»*에는
    구어 표지가 없다. **잡는 쪽을 넓히면 오탐이 반이 되고, 그러면 사람이 검사를 끈다.**
    안 잡는 것이 손해가 아닌 이유는 그 다섯이 **남겨야 할 자료**이기 때문이다.
    """
    assert not _said('*"왠지 모르겠는데 별로"*\n')
    assert not _said('*"뭐가 뭔지 모르겠다"*\n')


def test_들여쓴_블록은_안_본다() -> None:
    """`재현`·`강제자` 칸과 코드다. **산문이 아니다.**"""
    assert not _said('    사용자가 말했다 — *"이거 맞아?"*\n')


# ------------------------------------------------------------------ 저장소


def test_저장소가_0건이다() -> None:
    """**지금 0이 아니면 이 관문을 켤 수 없다** (D-0438이 52곳을 소급해 고쳤다)."""
    text = (ROOT / STYLE.PAST).read_text(encoding="utf-8")
    assert _said(text) == []


def test_그물이_안_비었다() -> None:
    """**0건이 «규칙이 돈다»는 뜻이 아니다** (D-0230).

    고치기 전 판을 넣어 본다. 안 잡히면 셈이 죽은 것이고, 그때도 저장소는 초록이다.
    """
    before = (
        "## D-0366. 거울\n\n"
        "사용자가 그 자리에서 짚었다: *«아니 왜 두 벌이 되는 거야? 기존 걸 날리면 되지 않냐.»*\n"
    )
    assert len(_said(before)) == 1


def test_홀로_돌_때도_같은_답을_낸다(capsys: pytest.CaptureFixture[str]) -> None:
    """`main()`을 실제로 지난다 (D-0432).

    D-0438의 `재현` 칸이 `python3 tools/doc_speech.py`를 적는다. **적어 둔 명령이
    안 돌면 틀린 안내다** (D-0292). 셈을 다시 재지 않는다 — 여기서 보는 것은
    **그 셈이 입구에 걸려 있는가**다 (D-0126).
    """
    assert SPEECH.main() == 0
    assert "0건" in capsys.readouterr().out


def test_기록_번호를_같이_찍는다() -> None:
    """**어느 판인지 안 적으면 3만 5천 줄에서 못 찾는다** (D-0203)."""
    text = "## D-0366. 거울\n\n본문\n"
    assert SPEECH.record_of(text, 3) == "D-0366"
    assert SPEECH.record_of("머리말\n", 1) == "(머리말)"


def test_입구에_걸려_있다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**안 걸면 안 돈다** (D-0126 · D-0432).

    셈을 가짜로 바꿔 **`check()`가 그것을 들고 오는지** 본다. `check()`에서
    `check_speech` 줄을 지우면 이 시험이 운다 — 셈만 맞고 배선이 없는 꼴을 막는다.
    """
    style: ModuleType = STYLE
    monkeypatch.setattr(style, "speech", lambda text, allow: [(7, "이거 맞아?")])

    problems = style.check()

    assert [one for one in problems if "D-0438" in one], "구어체 검사가 입구에 없다"
    assert sum("D-0438" in one for one in problems) == 1, "과거 축 말고 다른 문서에도 걸었다"


# ------------------------------------------------- D-0443이 연 구멍 셋


def test_뒷줄_표지가_앞_인용을_안_덮는다() -> None:
    """**표지는 인용이 시작하는 줄에서만 센다** (D-0443).

    걸친 줄을 전부 보면 다음 인용을 위해 붙인 표지가 앞 인용까지 덮는다. 실측으로
    D-0368이 그렇게 빠져나갔고, **D-0438은 그것을 0건이라 적었다.**
    """
    shielded = (
        "- **배경**: 꾸러미로 보냈다 — *«보면 바로 이해가 될거임\n"
        f"  백문이불여일견»*. 그가 짚었다:  {SPEECH.SPEECH_OK}\n"
    )
    assert _said(shielded), "뒷줄 표지가 앞 인용을 덮는다"


def test_표지가_규칙마다_따로다() -> None:
    """**표지 하나가 규칙 둘을 겸하면 한쪽이 다른 쪽을 덮는다** (D-0443).

    규칙 4(경어체·명령형)의 표지가 붙은 자리 다섯이 규칙 10에서 조용히 빠졌다.
    """
    assert SPEECH.SPEECH_OK != ALLOW
    line = '사용자가 물었다 — *"이거 맞아?"*'
    assert _said(f"{line}  {ALLOW}\n"), "규칙 4 표지가 규칙 10을 덮는다"
    assert not _said(f"{line}  {SPEECH.SPEECH_OK}\n")


def test_격식체여도_발화를_옮기면_잡는다() -> None:
    """**말투만 보면 모자란다** (D-0443).

    D-0437의 표가 그랬다 — 걸릴 낱말이 없는 발화 인용이다. 귀속 서술이 **인용 바로
    앞**에 붙어 있을 때만 센다. 창으로 훑으면 오탐이 반이 된다 (D-0438 실측 25/50).
    """
    assert _said('- **배경**: 사용자가 말했다 — *"잘 잡은 것 같다"*\n')
    assert not _said('- **배경**: 그 기록이 *"지표가 목표가 된다"*고 적었다.\n')
    assert not _said('- **배경**: D-0094가 *"지표가 목표가 된다"*고 적었다.\n')


# ------------------------------------------------- 욕설은 어디 있든 (D-0443)

# **글자를 쪼개 쓴다.** 이 파일에 통째로 적으면 검사가 제 시험을 문다 — 예외를
# 둘로 늘리면 숨을 자리가 둘이 된다.
CURSE = "씨" + "발"
SLANG = "졸" + "라"


def test_욕설을_잡는다(tmp_path: Path) -> None:
    """**사용자가 넷을 찾아 왔고 내 검사는 0건을 찍고 있었다** (D-0443)."""
    (tmp_path / "a.md").write_text(f"사용자의 말 그대로 *«뭐여 {CURSE}.»*\n", encoding="utf-8")

    assert SPEECH.profanity(tmp_path, ["a.md"]), "욕설을 못 잡는다"


def test_문서_밖도_본다(tmp_path: Path) -> None:
    """**시험 파일에 복사돼 있었다** (D-0443).

    말투 검사는 결정 기록만 본다. 욕설은 **추적 파일 전부**에서 0이어야 한다.
    """
    (tmp_path / "core").mkdir()
    (tmp_path / "core" / "t.py").write_text(f'"""{SLANG} 좋은데."""\n', encoding="utf-8")

    assert SPEECH.profanity(tmp_path, ["core/t.py"]), "문서 밖을 안 본다"


@pytest.mark.parametrize("line", ["동시발음 3", "장비가 있어야 도는 도구라면", "개인 연구라도"])
def test_앞_글자가_붙으면_낱말이_아니다(tmp_path: Path, line: str) -> None:
    """실측 오탐 6건이 전부 이 꼴이다 — `동시발음` · `도구라면` · `연구라도`."""
    (tmp_path / "a.md").write_text(line + "\n", encoding="utf-8")

    assert not SPEECH.profanity(tmp_path, ["a.md"]), f"오탐: {line}"


def test_저장소에_욕설이_0건이다() -> None:
    """**지금 0이 아니면 이 관문을 켤 수 없다.**"""
    assert SPEECH.profanity(ROOT, SPEECH.tracked_files(ROOT)) == []


def test_욕설_검사가_입구에_걸려_있다(monkeypatch: pytest.MonkeyPatch) -> None:
    """**안 걸면 안 돈다** (D-0126). `check()`가 들고 오는지 본다."""
    style: ModuleType = STYLE
    monkeypatch.setattr(style, "profanity", lambda root, tracked: [("a.md", 7, "x")])

    assert [one for one in style.check() if "D-0443" in one], "욕설 검사가 입구에 없다"
