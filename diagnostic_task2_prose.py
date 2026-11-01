"""Diagnostic analysis of Task 2 prose to understand extraction failures.

Analyzes the 1,483 char prose to identify:
1. Location transitions (where they occur)
2. Activity transitions (where they occur)
3. Exact evidence text with character offsets
4. Why the extractor missed protagonist.activity
"""

from pathlib import Path

# Read the actual prose from Task 2
prose_file = Path("output/stage10_task2/chapter_task2_001.txt")
with open(prose_file, "r", encoding="utf-8") as f:
    content = f.read()

# Extract prose only (remove header and metadata)
lines = content.split("\n")
prose_start = 0
prose_end = len(lines)

# Find prose boundaries
for i, line in enumerate(lines):
    if line.strip() == "---":
        prose_end = i
        break
    if i == 0 or (i == 1 and lines[i-1].startswith("#")):
        continue
    if prose_start == 0 and line.strip():
        prose_start = i

prose = "\n".join(lines[prose_start:prose_end])

print("=" * 80)
print("Task 2 Prose Diagnostic Analysis")
print("=" * 80)
print()
print(f"Total length: {len(prose)} chars")
print()

# Analyze location transitions
print("=" * 80)
print("Location Transitions")
print("=" * 80)
print()

location_keywords = [
    "市图书馆门前",
    "推开了那扇门",
    "图书馆内部",
    "穿过一排排书架",
    "科学类书籍区",
    "书架",
    "图书馆的阅览区在二楼",
    "二楼",
    "选了一个靠窗的位置",
    "阅览区",
]

for keyword in location_keywords:
    pos = prose.find(keyword)
    if pos != -1:
        # Get context (30 chars before and after)
        start = max(0, pos - 30)
        end = min(len(prose), pos + len(keyword) + 30)
        context = prose[start:end]
        print(f"Found: '{keyword}' at position {pos}")
        print(f"  Context: ...{context}...")
        print()

# Analyze activity transitions
print("=" * 80)
print("Activity Transitions (Reading)")
print("=" * 80)
print()

activity_keywords = [
    "打开了书",
    "开始读",
    "阅读",
    "读得很慢",
    "读到了",
    "继续阅读",
    "读懂一个概念",
    "读了将近两个小时",
    "读完",
    "重新翻开了书",
]

for keyword in activity_keywords:
    pos = prose.find(keyword)
    if pos != -1:
        start = max(0, pos - 30)
        end = min(len(prose), pos + len(keyword) + 30)
        context = prose[start:end]
        print(f"Found: '{keyword}' at position {pos}")
        print(f"  Context: ...{context}...")
        print()

# Identify the KEY moments for extraction
print("=" * 80)
print("Key Extraction Targets")
print("=" * 80)
print()

# Location transition
location_text = "图书馆的阅览区在二楼。李明选了一个靠窗的位置坐下"
loc_pos = prose.find(location_text)
if loc_pos != -1:
    print("LOCATION TRANSITION:")
    print(f"  Position: {loc_pos}")
    print(f"  Text: {location_text}")
    print(f"  Fact: protagonist.location = '图书馆二楼阅览区靠窗位置'")
    print()

# Activity transition - FIRST reading moment
activity_text = "他调整了一下坐姿，打开了书的第一页"
act_pos = prose.find(activity_text)
if act_pos != -1:
    print("ACTIVITY TRANSITION (Start Reading):")
    print(f"  Position: {act_pos}")
    print(f"  Text: {activity_text}")
    print(f"  Fact: protagonist.activity = 'reading'")
    print()

# Activity continuation - evidence of sustained reading
reading_evidence = [
    "李明一开始读得很慢，每一句话都要在脑海中细细咀嚼",
    "李明已经完全沉浸在书中了",
    "他读到了伽利略和牛顿",
    "李明又低下头，继续阅读",
    "李明活动了一下有些僵硬的脖子，才发现自己已经读了将近两个小时",
]

print("SUSTAINED READING EVIDENCE:")
for evidence in reading_evidence:
    pos = prose.find(evidence)
    if pos != -1:
        print(f"  [{pos}] {evidence}")
print()

# Analyze what the extractor actually found
print("=" * 80)
print("What Extractor Found (from Task 2)")
print("=" * 80)
print()

print("Operation 1:")
print("  fact_path: protagonist.location")
print("  value: 市图书馆门前")
print("  evidence: chapter:12-67")
print("  Status: ✓ VALID")
print()

print("Operation 2:")
print("  fact_path: protagonist.location")
print("  value: 图书馆二楼阅览区靠窗位置")
print("  evidence: chapter:654-705")
print("  Status: ✓ VALID")
print()

print("Missing Operation:")
print("  fact_path: protagonist.activity")
print("  value: reading")
print("  evidence: SHOULD BE around position", act_pos if act_pos != -1 else "NOT FOUND")
print("  Status: ✗ NOT EXTRACTED")
print()

# Analyze WHY activity was missed
print("=" * 80)
print("Root Cause Analysis")
print("=" * 80)
print()

print("Issue 1: Evidence text restrictions")
print("  The prompt forbids quotes in JSON strings")
print("  This forces LLM to modify evidence text")
print("  Modified text doesn't match prose exactly")
print("  Evidence verification rejects it")
print()

print("Issue 2: Activity detection")
print("  'reading' is mentioned throughout the prose")
print("  But transition moment is: '打开了书的第一页'")
print("  LLM may focus on explicit 'reading' keyword")
print("  Misses the ACTION that initiates reading state")
print()

print("Issue 3: Multiple location changes")
print("  LLM extracted 2 location operations")
print("  But only 1 activity operation needed")
print("  Coverage calculation: 2 ops / 2 requirements = 100%")
print("  Actually: location ✓, activity ✗ = 50%")
print()

print("=" * 80)
print("Recommended Fixes")
print("=" * 80)
print()

print("1. ALLOW QUOTES IN EVIDENCE")
print("   Remove the quote restriction from prompt")
print("   Use JSON escaping properly")
print("   Let LLM provide exact prose excerpts")
print()

print("2. ENHANCE ACTIVITY DETECTION")
print("   Explicitly ask for ACTION verbs that initiate states")
print("   Examples: 打开书 = start reading, 合上书 = stop reading")
print("   Distinguish: intent vs action vs current state")
print()

print("3. FIX COVERAGE CALCULATION")
print("   Match operations to specific required transitions")
print("   Count by transition type, not just operation count")
print("   Report: protagonist.location ✓, protagonist.activity ✗")
print()

print("4. VERIFY EVIDENCE PROGRAMMATICALLY")
print("   Use fuzzy matching to find approximate evidence")
print("   Calculate actual character offsets in prose")
print("   Reject if similarity < threshold")
print()

print("=" * 80)
print("End of Diagnostic")
print("=" * 80)
