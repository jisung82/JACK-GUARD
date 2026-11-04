"""CMD-style color attributes. No shell invocation and no arbitrary stylesheet input."""

from jack_guard.ui.design import STYLE

# Classic console color table. Like CMD, the host's original theme is restored by COLOR alone.
PALETTE = (
    "#000000",
    "#000080",
    "#008000",
    "#008080",
    "#800000",
    "#800080",
    "#808000",
    "#C0C0C0",
    "#808080",
    "#0000FF",
    "#00FF00",
    "#00FFFF",
    "#FF0000",
    "#FF00FF",
    "#FFFF00",
    "#FFFFFF",
)

COLOR_HELP = """COLOR [attr]
현재 JACK GUARD 창의 배경색과 글자색을 변경합니다.
  두 자리: 첫째 = 배경, 둘째 = 글자. 한 자리: 검정 배경 + 해당 글자색.
  color      시작 시 기본 테마 복원
  color /?   이 도움말

  0 검정       8 회색
  1 파랑       9 밝은 파랑
  2 녹색       A 밝은 녹색
  3 청록       B 밝은 청록
  4 빨강       C 밝은 빨강
  5 자주       D 밝은 자주
  6 노랑       E 밝은 노랑
  7 흰색       F 밝은 흰색

예: color 0A / color 1F / color F0 / color A
대소문자 구분 없음. 같은 배경·글자 코드는 변경하지 않고 ERRORLEVEL 1.
현재 창에만 적용되며 재시작하면 기본 테마를 사용합니다."""


def parse_color(argument):
    if not isinstance(argument, str) or not 1 <= len(argument) <= 2:
        raise ValueError("COLOR: 16진수 한 자리 또는 두 자리만 사용하세요. color /?")
    if any(c not in "0123456789abcdefABCDEF" for c in argument):
        raise ValueError("COLOR: 0~9, A~F만 사용하세요. color /?")
    code = argument.upper().zfill(2)
    if code[0] == code[1]:
        raise ValueError("COLOR: 배경색과 글자색이 같습니다. 기존 색상을 유지합니다.")
    return code, (PALETTE[int(code[0], 16)], PALETTE[int(code[1], 16)])


def border_color(background, foreground):
    channels = [
        round(int(background[i : i + 2], 16) * 0.6 + int(foreground[i : i + 2], 16) * 0.4)
        for i in (1, 3, 5)
    ]
    return "#" + "".join(f"{value:02X}" for value in channels)


def color_stylesheet(background, foreground):
    border = border_color(background, foreground)
    replacements = {
        "#090B0D": background,
        "#101316": background,
        "#171B1F": border,
        "#2A3035": border,
        "#E6E8EA": foreground,
        "#89939B": foreground,
        "#58626B": foreground,
        "#B8F36B": foreground,
        "#36492A": foreground,
    }
    # Replace original tokens in one pass; a chosen color may equal another original token.
    import re

    themed = re.sub(r"#[0-9A-Fa-f]{6}", lambda m: replacements.get(m[0], m[0]), STYLE)
    return themed + f"\nQWidget {{ selection-color:{background}; }}\n"
