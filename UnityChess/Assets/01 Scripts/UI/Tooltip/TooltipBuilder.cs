using entity.targetable;
using ui.view.unit;
using core.data;

namespace ui.tooltip
{
    /// <summary>
    /// 툴팁 데이터를 생성하는 빌더 클래스
    /// </summary> 
    public static class TooltipBuilder
    {
        public static TooltipData UnitCardTooltip(CardDefinition def)
        {
            return new TooltipData(
                title: def.card.name,
                header: $"[유닛/클래스 : {def.card.unitType}]",
                description: $"[{def.evt.timing}] {def.evt.name}: {def.evt.text}" + "\n\n" +
                $"공격력: {def.card.attack}    체력: {def.card.hp}"
            );
        }

        public static TooltipData SpellCardTooltip(CardDefinition def)
        {
            return new TooltipData(
                title: def.card.name,
                header: $"[스펠/클래스 : {def.card.unitType}]",
                description: $"{def.effect.name}: {def.effect.text}"
            );
        }

        // 유닛과 효과 설명을 함께 표시하는 카드 툴팁 (후보)
        public static TooltipData CadTooltip(CardDefinition def)
        {
            return new TooltipData(
                title: def.card.name,
                header: $"[카드/클래스 : {def.card.unitType}]",
                description: $"[{def.evt.timing}] {def.evt.name}: {def.evt.text}" + "\n\n" +
                $"{def.effect.name}: {def.effect.text}" + "\n\n" +
                $"공격력: {def.card.attack}    체력: {def.card.hp}"
            );
        }

        public static TooltipData UnitOnboardTooltip(CardDefinition def, UnitViewData data)
        {
            return new TooltipData(
                title: def.card.name,
                header: $"[유닛/클래스 : {def.card.unitType}]",
                description: $"[{def.evt.timing}] {def.evt.name}: {def.evt.text}" + "\n\n" +
                $"공격력: {def.card.attack}    체력: {data.curHP} / {def.card.hp}"
            );
        }
    }
}