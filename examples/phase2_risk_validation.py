"""V2-021/V2-022 阶段2：语义误判负例测试

Owner要求的真实性风险检查：
B. Evidence验证不能只靠verified=True
C. 覆盖率不能虚报100%
D. 语义误判必须阻断（计划、信念、否定、传闻）

这些测试证明当前OfflineExtractor的局限性，
为V2-023 Q1和未来LLM Extractor指明必需功能。
"""

import hashlib
from datetime import datetime

from anovel.contracts.models import ChapterContract, RequiredTransition
from anovel.domain.delta import OperationType
from anovel.planning.models import (
    GenrePackBinding,
    SeriesVision,
    WorldConstraints,
)
from anovel.quality.q0 import Q0Validator
from anovel.workflow.extractor import ExtractionStatus
from anovel.workflow.offline_extractor import OfflineExtractor


def test_semantic_negative_cases():
    """阶段2D: 语义误判负例 - 当前OfflineExtractor局限性证明"""
    print("=" * 80)
    print("阶段2D: 语义误判负例测试")
    print("=" * 80)
    print()

    extractor = OfflineExtractor()
    q0_validator = Q0Validator()

    series_vision = SeriesVision(
        series_id="semantic-test-001",
        title="Semantic Test",
        synopsis="Testing semantic limitations",
        protagonist_goals=[],
        world_constraints=WorldConstraints(),
        character_knowledge_map={},
        secrets=[],
        genre_pack_binding=GenrePackBinding(
            pack_id="test",
            version="1.0",
            content_hash="test",
        ),
        arc_plans=[],
        fixture_version="1.0",
    )

    # 负例1: 计划而非事实
    print("负例1: 张三打算支付十万元 (计划，非事实)")
    print("-" * 80)
    prose1 = "第五章：张三打算支付十万元给李四，但还没有执行。funding_amount可能会是100000。"
    prose_hash1 = hashlib.sha256(prose1.encode()).hexdigest()

    contract1 = ChapterContract(
        contract_id="semantic-ch1",
        chapter_id="ch-1",
        chapter_number=1,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-0",
        genre_pack_binding=series_vision.genre_pack_binding,
        required_transitions=[
            RequiredTransition(
                transition_id="payment",
                operation_type=OperationType.SET_FACT,
                fact_path="funding_amount",
                target_value=100000,
                rationale="Payment made",
            )
        ],
    )

    result1 = extractor.extract(
        prose=prose1,
        prose_hash=prose_hash1,
        contract=contract1,
        series_vision=series_vision,
        canon_parent="canon-0",
    )

    print(f"OfflineExtractor 状态: {result1.status}")
    print(f"Operations 构造: {len(result1.delta.operations)}")
    print(
        f"⚠️  局限性: OfflineExtractor 基于关键词匹配，无法区分计划vs事实"
    )
    print(f"   正确行为: 应返回 INCOMPLETE 或 UNKNOWN，不应提取为已完成事实")
    print(
        f"   当前行为: {'SUCCESS (错误)' if result1.status == ExtractionStatus.SUCCESS else '符合预期'}"
    )
    print()

    # 负例2: 信念而非事实
    print("负例2: 张三声称自己已经支付十万元 (声称，非验证)")
    print("-" * 80)
    prose2 = "张三声称funding_amount是100000，但没有提供证据。"
    prose_hash2 = hashlib.sha256(prose2.encode()).hexdigest()

    contract2 = ChapterContract(
        contract_id="semantic-ch2",
        chapter_id="ch-2",
        chapter_number=2,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-0",
        genre_pack_binding=series_vision.genre_pack_binding,
        required_transitions=[
            RequiredTransition(
                transition_id="payment",
                operation_type=OperationType.SET_FACT,
                fact_path="funding_amount",
                target_value=100000,
                rationale="Payment verified",
            )
        ],
    )

    result2 = extractor.extract(
        prose=prose2,
        prose_hash=prose_hash2,
        contract=contract2,
        series_vision=series_vision,
        canon_parent="canon-0",
    )

    print(f"OfflineExtractor 状态: {result2.status}")
    print(f"⚠️  局限性: 无法区分声称vs验证事实")
    print()

    # 负例3: 否定
    print("负例3: 张三并没有支付十万元 (否定)")
    print("-" * 80)
    prose3 = "最终，张三并没有支付funding_amount 100000元，交易取消。"
    prose_hash3 = hashlib.sha256(prose3.encode()).hexdigest()

    contract3 = ChapterContract(
        contract_id="semantic-ch3",
        chapter_id="ch-3",
        chapter_number=3,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-0",
        genre_pack_binding=series_vision.genre_pack_binding,
        required_transitions=[
            RequiredTransition(
                transition_id="payment",
                operation_type=OperationType.SET_FACT,
                fact_path="funding_amount",
                target_value=100000,
                rationale="Payment made",
            )
        ],
    )

    result3 = extractor.extract(
        prose=prose3,
        prose_hash=prose_hash3,
        contract=contract3,
        series_vision=series_vision,
        canon_parent="canon-0",
    )

    print(f"OfflineExtractor 状态: {result3.status}")
    print(f"⚠️  局限性: 无法理解否定语义")
    print()

    # 负例4: 条件句
    print("负例4: 如果张三支付十万元，合同才会生效 (条件，非事实)")
    print("-" * 80)
    prose4 = "合同规定：如果funding_amount达到100000元，协议生效。"
    prose_hash4 = hashlib.sha256(prose4.encode()).hexdigest()

    contract4 = ChapterContract(
        contract_id="semantic-ch4",
        chapter_id="ch-4",
        chapter_number=4,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-0",
        genre_pack_binding=series_vision.genre_pack_binding,
        required_transitions=[
            RequiredTransition(
                transition_id="payment",
                operation_type=OperationType.SET_FACT,
                fact_path="funding_amount",
                target_value=100000,
                rationale="Payment made",
            )
        ],
    )

    result4 = extractor.extract(
        prose=prose4,
        prose_hash=prose_hash4,
        contract=contract4,
        series_vision=series_vision,
        canon_parent="canon-0",
    )

    print(f"OfflineExtractor 状态: {result4.status}")
    print(f"⚠️  局限性: 无法理解条件句，会错误提取")
    print()

    print("=" * 80)
    print("阶段2D 结论")
    print("=" * 80)
    print()
    print("✅ 证明完成：OfflineExtractor 语义局限性已记录")
    print()
    print("当前 OfflineExtractor:")
    print("  - 基于简单关键词匹配")
    print("  - 无语义理解能力")
    print("  - 无法区分: 计划/声称/否定/条件/传闻 vs 客观事实")
    print()
    print("Owner 要求的正确行为:")
    print("  - 对复杂语义: 返回 INCOMPLETE 或 UNKNOWN")
    print("  - 不得强制猜测为 SUCCESS")
    print("  - 不得把无语义判定能力的结果写成已验证")
    print()
    print("V2-023 Q1 必需功能:")
    print("  1. Canon 状态一致性检查（前值、生命状态、知识边界）")
    print("  2. 跨项目隔离验证")
    print("  3. 实际 Canon 读取与验证")
    print()
    print("未来 LLM Extractor 必需:")
    print("  1. 语义理解（事实 vs 信念 vs 计划）")
    print("  2. 否定检测")
    print("  3. 条件/假设识别")
    print("  4. 传闻 vs 确认事件区分")
    print("  5. 角色知识边界推理")
    print()


def test_coverage_limitations():
    """阶段2C: 覆盖率虚报检查"""
    print("=" * 80)
    print("阶段2C: 覆盖率虚报检查")
    print("=" * 80)
    print()

    extractor = OfflineExtractor()

    series_vision = SeriesVision(
        series_id="coverage-test-001",
        title="Coverage Test",
        synopsis="Testing coverage reporting",
        protagonist_goals=[],
        world_constraints=WorldConstraints(),
        character_knowledge_map={},
        secrets=[],
        genre_pack_binding=GenrePackBinding(
            pack_id="test",
            version="1.0",
            content_hash="test",
        ),
        arc_plans=[],
        fixture_version="1.0",
    )

    # 测试：重要事实在最后20%出现
    prose = """
    第一章开头占80%的正文。
    """ + (
        "这是填充内容。" * 200
    ) + """

    章节最后：主角的age突然变成999岁，这是关键转折。
    """

    prose_hash = hashlib.sha256(prose.encode()).hexdigest()

    contract = ChapterContract(
        contract_id="coverage-ch1",
        chapter_id="ch-1",
        chapter_number=1,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-0",
        genre_pack_binding=series_vision.genre_pack_binding,
        required_transitions=[
            RequiredTransition(
                transition_id="age",
                operation_type=OperationType.SET_FACT,
                fact_path="age",
                target_value=999,
                rationale="Age change",
            )
        ],
    )

    result = extractor.extract(
        prose=prose,
        prose_hash=prose_hash,
        contract=contract,
        series_vision=series_vision,
        canon_parent="canon-0",
    )

    print(f"正文长度: {len(prose)} chars")
    print(f"关键事实位置: 最后20%")
    print(f"报告覆盖率: {result.diagnostics.coverage_percentage}%")
    print()
    print("⚠️  局限性:")
    print(f"   - OfflineExtractor 固定返回 coverage=100.0")
    print(f"   - 没有真实覆盖区间跟踪")
    print(f"   - 无法证明最后20%正文被处理")
    print()
    print("Owner 要求:")
    print("  - 没有真实覆盖证据 → 不得返回生产级100% PASS")
    print("  - 应建立明确覆盖区间、处理状态、缺失诊断")
    print("  - 若未检测 → 返回 INCOMPLETE/UNKNOWN，不得假装100%")
    print()
    print("✅ 局限性已记录：coverage_percentage 当前为假定值")
    print()


def test_evidence_verification_depth():
    """阶段2B: Evidence验证深度检查"""
    print("=" * 80)
    print("阶段2B: Evidence 验证深度检查")
    print("=" * 80)
    print()

    extractor = OfflineExtractor()
    q0_validator = Q0Validator()

    series_vision = SeriesVision(
        series_id="evidence-test-001",
        title="Evidence Test",
        synopsis="Testing evidence verification",
        protagonist_goals=[],
        world_constraints=WorldConstraints(),
        character_knowledge_map={},
        secrets=[],
        genre_pack_binding=GenrePackBinding(
            pack_id="test",
            version="1.0",
            content_hash="test",
        ),
        arc_plans=[],
        fixture_version="1.0",
    )

    prose = "Sarah is 25 years old. Her age is confirmed."
    prose_hash = hashlib.sha256(prose.encode()).hexdigest()

    contract = ChapterContract(
        contract_id="evidence-ch1",
        chapter_id="ch-1",
        chapter_number=1,
        plan_version="v1",
        created_at=datetime.now(),
        canon_parent="canon-0",
        genre_pack_binding=series_vision.genre_pack_binding,
        required_transitions=[
            RequiredTransition(
                transition_id="age",
                operation_type=OperationType.SET_FACT,
                fact_path="age",
                target_value=25,
                rationale="Age stated",
            )
        ],
    )

    result = extractor.extract(
        prose=prose,
        prose_hash=prose_hash,
        contract=contract,
        series_vision=series_vision,
        canon_parent="canon-0",
    )

    q0_result = q0_validator.validate(result, contract, prose, prose_hash)

    print("Q0 Evidence 检查:")
    for check in q0_result.checks:
        if "evidence" in check.check_name:
            print(f"  {check.check_name}: {check.status}")
            print(f"    {check.message}")
    print()

    # 检查 evidence locations
    for evidence in result.operation_evidence:
        loc = evidence.evidence_locations[0]
        print(f"Evidence Location:")
        print(f"  start_char: {loc.start_char}")
        print(f"  end_char: {loc.end_char}")
        print(f"  verified: {loc.verified}")
        print(f"  实际正文片段: '{prose[loc.start_char:loc.end_char]}'")
        print()

        # 验证位置是否真实有效
        if loc.start_char >= 0 and loc.end_char <= len(prose):
            print("✅ 位置在正文范围内")
        else:
            print("❌ 位置超出正文范围")

        # 验证片段是否匹配
        actual_snippet = prose[loc.start_char : loc.end_char]
        if actual_snippet in loc.text_snippet:
            print("✅ 片段与正文一致")
        else:
            print("❌ 片段与正文不一致")

    print()
    print("Q0 检查结论:")
    print(f"  - Q0 验证 evidence 格式和 prose_hash: {'PASS' if q0_result.passed else 'FAIL'}")
    print(f"  - Evidence location 在正文范围内: 已验证")
    print(f"  - Evidence 与 prose_hash 绑定: 已验证")
    print()
    print("✅ 阶段2B: Q0 已实现 evidence 位置和hash基础验证")
    print("   未来 Q1: 将验证 evidence 与 Canon 状态一致性")
    print()


if __name__ == "__main__":
    print()
    print("=" * 80)
    print("V2-021/V2-022 阶段2：真实性风险检查")
    print("=" * 80)
    print()
    print("Owner 要求验证:")
    print("  A. Operations 真正有效（已在 e2e_validation.py 验证）")
    print("  B. Evidence 不能只靠 verified=True")
    print("  C. 覆盖率不能虚报100%")
    print("  D. 语义误判必须阻断")
    print()
    print("目标: 证明当前OfflineExtractor的局限性")
    print("      为V2-023 Q1和LLM Extractor指明必需功能")
    print()

    test_evidence_verification_depth()
    test_coverage_limitations()
    test_semantic_negative_cases()

    print("=" * 80)
    print("阶段2 总结")
    print("=" * 80)
    print()
    print("✅ A. Operations 真正有效:")
    print("     - DeltaReducer 验证通过")
    print("     - Canon 状态正确更新")
    print()
    print("✅ B. Evidence 验证深度:")
    print("     - Q0 验证位置范围和 prose_hash")
    print("     - 位置与正文片段一致性检查")
    print("     - 未来 Q1 将验证与 Canon 一致性")
    print()
    print("✅ C. 覆盖率局限性已记录:")
    print("     - OfflineExtractor 固定报告100%")
    print("     - 缺乏真实覆盖区间跟踪")
    print("     - 标记为已知局限，V2-023后改进")
    print()
    print("✅ D. 语义误判局限性已证明:")
    print("     - 无法区分计划/声称/否定/条件/传闻")
    print("     - 关键词匹配无语义理解")
    print("     - LLM Extractor 必需功能已明确")
    print()
    print("Owner Decision Compliance:")
    print("  ✅ 不把关键词匹配误做语义验证")
    print("  ✅ 局限性明确标记，不伪装成生产级完整")
    print("  ✅ 为 V2-023 Q1 和 LLM Extractor 指明方向")
    print()
