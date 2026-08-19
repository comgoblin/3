# -*- coding: utf-8 -*-
"""
윈도우11 설치 시뮬레이터 - 오류/버그 검사 루틴
===============================================
사용법:
    python check_simulator.py                     # 폴더 안의 가장 최신(버전 번호 최대) HTML 파일 자동 검사
    python check_simulator.py 파일명.html           # 특정 파일 지정 검사
    python check_simulator.py --all                # v1~v6 등 모든 시뮬레이터 HTML 파일 검사

검사 항목:
    1. 화면(scene) 정의 중복 키
    2. go / accept.go 가 가리키는 화면이 실제로 존재하는지
    3. ORDER 배열과 화면 정의(S) 간 불일치 (빠짐 / 순서에 없는 화면)
    4. 도움말 topic 참조가 HELP / HELPORDER 에 실제로 존재하는지
    5. 이미지(src, frames) 파일이 실제 폴더에 존재하는지 (PATCHED 매핑 반영)
    6. 사용되지 않는(고아) 이미지 파일 (참고용, 오류 아님)
    7. <script> 안 괄호類({ } ( ) [ ]) 균형 (기초 문법 점검)

버그를 새로 못 잡아도, 화면 연결이 끊기거나 이미지 경로가 어긋나는 흔한 실수를
5초 안에 잡아내는 것이 목적입니다. 파일을 수정할 때마다 실행하세요.
"""
import re
import sys
import glob
import os
import datetime

# Windows 콘솔(cp949 등)에서도 이모지/한글이 깨지지 않도록 UTF-8로 강제
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def find_latest_html():
    files = glob.glob(os.path.join(BASE_DIR, "윈도우11_설치_시뮬레이터_v*.html"))
    def ver(f):
        m = re.search(r"_v(\d+)\.html$", f)
        return int(m.group(1)) if m else -1
    if not files:
        return None
    return max(files, key=ver)


def find_all_html():
    files = glob.glob(os.path.join(BASE_DIR, "윈도우11_설치_시뮬레이터_v*.html"))
    def ver(f):
        m = re.search(r"_v(\d+)\.html$", f)
        return int(m.group(1)) if m else -1
    return sorted(files, key=ver)


def extract_block(text, start_marker, open_ch="{", close_ch="}"):
    """start_marker 이후 첫 open_ch 부터 짝이 맞는 close_ch 까지 반환"""
    i = text.find(start_marker)
    if i == -1:
        return None, -1, -1
    i = text.find(open_ch, i)
    if i == -1:
        return None, -1, -1
    depth = 0
    j = i
    in_str = None
    esc = False
    while j < len(text):
        c = text[j]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == in_str:
                in_str = None
        else:
            if c in ("'", '"', "`"):
                in_str = c
            elif c == open_ch:
                depth += 1
            elif c == close_ch:
                depth -= 1
                if depth == 0:
                    return text[i:j+1], i, j+1
        j += 1
    return None, i, -1


def split_top_level_entries(block_text):
    """블록(예: S={...}) 안에서 줄 맨 앞에 오는 `key: {` 패턴 기준으로 항목을 나눈다."""
    entries = {}
    order = []
    matches = list(re.finditer(r"(?:^|\n)([A-Za-z_$][\w$]*)\s*:\s*\{", block_text))
    for idx, m in enumerate(matches):
        key = m.group(1)
        start = m.start(1)
        end = matches[idx+1].start(1) if idx+1 < len(matches) else len(block_text)
        entries.setdefault(key, []).append(block_text[start:end])
        order.append(key)
    return entries, order


def check_file(html_path):
    report = []
    ok = True
    name = os.path.basename(html_path)
    report.append(f"\n{'='*70}\n검사 대상: {name}\n{'='*70}")

    with open(html_path, "r", encoding="utf-8") as f:
        text = f.read()

    # ---------- script 태그 추출 ----------
    m = re.search(r"<script>(.*)</script>", text, re.S)
    if not m:
        report.append("  ❌ <script> 블록을 찾지 못했습니다.")
        return False, "\n".join(report)
    script = m.group(1)

    # ---------- 1) 괄호 균형 ----------
    pairs = {"{": "}", "(": ")", "[": "]"}
    closers = {v: k for k, v in pairs.items()}
    stack = []
    in_str = None
    esc = False
    in_tmpl_expr_depth = []  # not fully handling ${}; best-effort
    i = 0
    brace_issue = None
    while i < len(script):
        c = script[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == in_str:
                in_str = None
        else:
            if c in ("'", '"', "`"):
                in_str = c
            elif c == "/" and i+1 < len(script) and script[i+1] == "/":
                nl = script.find("\n", i)
                i = nl if nl != -1 else len(script)
                continue
            elif c == "/" and i+1 < len(script) and script[i+1] == "*":
                end = script.find("*/", i+2)
                i = end+2 if end != -1 else len(script)
                continue
            elif c in pairs:
                stack.append((c, i))
            elif c in closers:
                if not stack or stack[-1][0] != closers[c]:
                    line = script.count("\n", 0, i) + 1
                    brace_issue = f"  ❌ 괄호 불일치: 위치(스크립트 내 {line}번째 줄) '{c}' 앞에서 짝이 맞지 않습니다."
                    break
                stack.pop()
        i += 1
    if brace_issue:
        report.append(brace_issue)
        ok = False
    elif stack:
        c, pos = stack[-1]
        line = script.count("\n", 0, pos) + 1
        report.append(f"  ❌ 괄호가 닫히지 않았습니다: '{c}' (스크립트 내 {line}번째 줄 부근), 남은 미해결 {len(stack)}개")
        ok = False
    else:
        report.append("  ✅ 괄호({ } ( ) [ ]) 균형 정상")

    # ---------- 2) S 객체 파싱 ----------
    s_block, s_start, s_end = extract_block(script, "const S = ")
    if not s_block:
        report.append("  ❌ `const S = {...}` 화면 정의를 찾지 못했습니다.")
        return False, "\n".join(report)
    entries, order_seen = split_top_level_entries(s_block)

    dup = {k: v for k, v in entries.items() if len(v) > 1}
    if dup:
        ok = False
        for k, v in dup.items():
            report.append(f"  ❌ 화면 키 중복 정의: '{k}' ({len(v)}번 정의됨 — 마지막 정의만 실제로 사용됩니다)")
    else:
        report.append(f"  ✅ 화면(scene) 키 중복 없음 (총 {len(entries)}개)")

    scene_keys = set(entries.keys())

    # ---------- 3) go 대상 검증 ----------
    go_targets = set(re.findall(r'\bgo\s*:\s*"([^"]+)"', s_block))
    go_targets |= set(re.findall(r"\bgo\s*:\s*'([^']+)'", s_block))
    missing_go = sorted(t for t in go_targets if t not in scene_keys)
    if missing_go:
        ok = False
        report.append(f"  ❌ 존재하지 않는 화면을 가리키는 go 대상: {missing_go}")
    else:
        report.append(f"  ✅ go 대상 전부 유효함 (참조 {len(go_targets)}종)")

    # ---------- 4) ORDER 배열 검증 ----------
    order_block, _, _ = extract_block(script, "const ORDER = ", "[", "]")
    if order_block:
        order_list = re.findall(r'"([^"]+)"', order_block)
        missing_in_S = [k for k in order_list if k not in scene_keys]
        not_in_order = sorted(scene_keys - set(order_list))
        dup_in_order = [k for k in set(order_list) if order_list.count(k) > 1]
        if missing_in_S:
            ok = False
            report.append(f"  ❌ ORDER 배열에는 있지만 S에 없는 화면: {missing_in_S}")
        else:
            report.append(f"  ✅ ORDER 배열의 모든 항목이 S에 존재함 (총 {len(order_list)}단계)")
        if dup_in_order:
            ok = False
            report.append(f"  ❌ ORDER 배열에 중복된 화면: {dup_in_order}")
        if not_in_order:
            report.append(f"  ℹ 참고: S에는 있지만 ORDER 진행 목록에 없는 화면(의도된 것일 수 있음): {not_in_order}")
    else:
        report.append("  ⚠ `const ORDER = [...]` 를 찾지 못해 진행 순서 검증을 건너뜀")

    # ---------- 5) 도움말 topic 검증 ----------
    topics_ref = set(re.findall(r'\btopic\s*:\s*"([^"]+)"', s_block))
    help_block, _, _ = extract_block(script, "const HELP = ")
    if help_block:
        help_entries, _ = split_top_level_entries(help_block)
        help_keys = set(help_entries.keys())
        missing_topics = sorted(t for t in topics_ref if t not in help_keys)
        if missing_topics:
            ok = False
            report.append(f"  ❌ HELP에 없는 도움말 topic 참조: {missing_topics}")
        else:
            report.append(f"  ✅ 도움말 topic 참조 전부 유효함 (참조 {len(topics_ref)}종)")

        helporder_m = re.search(r'const HELPORDER = \[([^\]]+)\]', script)
        if helporder_m:
            helporder_list = re.findall(r'"([^"]+)"', helporder_m.group(1))
            missing_in_help = [k for k in helporder_list if k not in help_keys]
            not_in_helporder = sorted(help_keys - set(helporder_list))
            if missing_in_help:
                ok = False
                report.append(f"  ❌ HELPORDER에는 있지만 HELP에 없는 항목: {missing_in_help}")
            if not_in_helporder:
                report.append(f"  ℹ 참고: HELP에는 있지만 HELPORDER 메뉴에 없는 항목: {not_in_helporder}")
    else:
        report.append("  ⚠ `const HELP = {...}` 를 찾지 못해 도움말 검증을 건너뜀")

    # ---------- 6) 이미지 파일 존재 검증 ----------
    dir_m = re.search(r'const DIR\s*=\s*"([^"]+)"', script)
    dir2_m = re.search(r'const DIR2\s*=\s*"([^"]+)"', script)
    patched_m = re.search(r'const PATCHED\s*=\s*\{([^}]*)\}', script)
    DIR = dir_m.group(1) if dir_m else "윈도우11 25H2 온라인 설치/"
    DIR2 = dir2_m.group(1) if dir2_m else "시뮬레이터_이미지/"
    patched_files = set(re.findall(r'"([^"]+\.jpg)"', patched_m.group(1))) if patched_m else set()

    referenced_images = set()
    referenced_images |= set(re.findall(r'\bsrc\s*:\s*"([^"]+\.jpg)"', s_block))
    referenced_images |= set(re.findall(r'\ba\s*:\s*"([^"]+\.jpg)"', s_block))
    referenced_images |= set(re.findall(r'\bb\s*:\s*"([^"]+\.jpg)"', s_block))
    referenced_images |= set(re.findall(r'\bbase\s*:\s*"([^"]+\.jpg)"', s_block))
    for fr_block in re.findall(r'\bframes\s*:\s*\[([^\]]+)\]', s_block):
        referenced_images |= set(re.findall(r'"([^"]+\.jpg)"', fr_block))

    missing_images = []
    dir1_path = os.path.join(os.path.dirname(html_path), DIR)
    dir2_path = os.path.join(os.path.dirname(html_path), DIR2)
    used_dir1 = set()
    used_dir2 = set()
    for fn in sorted(referenced_images):
        target_dir = dir2_path if fn in patched_files else dir1_path
        if fn in patched_files:
            used_dir2.add(fn)
        else:
            used_dir1.add(fn)
        if not os.path.isfile(os.path.join(target_dir, fn)):
            missing_images.append(f"{fn}  (→ {DIR2 if fn in patched_files else DIR})")

    if missing_images:
        ok = False
        report.append(f"  ❌ 실제로 없는 이미지 파일 참조 ({len(missing_images)}개):")
        for mi in missing_images:
            report.append(f"      - {mi}")
    else:
        report.append(f"  ✅ 코드에서 참조하는 이미지 파일 {len(referenced_images)}개 전부 존재함")

    # ---------- 7) 사용되지 않는 이미지 (참고) ----------
    def list_dir_images(p):
        if not os.path.isdir(p):
            return set()
        return {f for f in os.listdir(p) if f.lower().endswith(".jpg")}
    actual_dir1 = list_dir_images(dir1_path)
    actual_dir2 = list_dir_images(dir2_path)
    unused1 = sorted(actual_dir1 - used_dir1)
    unused2 = sorted(actual_dir2 - used_dir2)
    if unused1 or unused2:
        total_unused = len(unused1) + len(unused2)
        report.append(f"  ℹ 참고: 코드에서 참조하지 않는 이미지 파일 {total_unused}개 (오류 아님, 다른 버전용일 수 있음)")

    status = "✅ 문제 없음" if ok else "❌ 문제 발견"
    report.append(f"\n  결과: {status}")
    return ok, "\n".join(report)


def main():
    args = sys.argv[1:]
    if args and args[0] == "--all":
        targets = find_all_html()
    elif args:
        p = args[0]
        targets = [p if os.path.isabs(p) else os.path.join(BASE_DIR, p)]
    else:
        latest = find_latest_html()
        targets = [latest] if latest else []

    if not targets:
        print("검사할 HTML 파일을 찾지 못했습니다.")
        sys.exit(1)

    all_ok = True
    full_report = []
    full_report.append(f"윈도우11 시뮬레이터 오류/버그 검사 리포트")
    full_report.append(f"실행 시각: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    for t in targets:
        if not os.path.isfile(t):
            print(f"파일을 찾을 수 없습니다: {t}")
            all_ok = False
            continue
        ok, rep = check_file(t)
        print(rep)
        full_report.append(rep)
        all_ok = all_ok and ok

    out_dir = os.path.join(BASE_DIR, "검사리포트")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"검사_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(full_report))
    print(f"\n리포트 저장됨: {out_path}")

    sys.exit(0 if all_ok else 2)


if __name__ == "__main__":
    main()
