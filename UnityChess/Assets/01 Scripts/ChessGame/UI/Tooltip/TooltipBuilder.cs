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
        // 유닛과 효과 설명을 함께 표시하는 카드 툴팁
        public static TooltipData CardTooltip(CardDefinition def)
        {
            return new TooltipData(
                title: def.card.name,
                header: $"[카드/클래스 : {ResolveClass(def.card.unitClass)}]",
                description: $"[{def.evt.timing}] {def.evt.name}: {def.evt.text}" + "\n\n" +
                $"{def.effect.name}: {def.effect.text}" + "\n\n" +
                $"공격력: {def.card.attack}    체력: {def.card.hp}"
            );
        }
        
        // 정보가 공개되지 않는 뒷면 상태인 상대 카드 툴팁
        public static TooltipData OpponentCardTooltip()
        {
            return new TooltipData(
                title: "???",
                header: "[카드/클래스 : ???]",
                description: "???"
            );
        }

        public static TooltipData UnitOnboardTooltip(CardDefinition def, UnitViewData data)
        {
            return new TooltipData(
                title: def.card.name,
                header: $"[유닛/클래스 : {ResolveClass(def.card.unitClass)}]",
                description: $"[{def.evt.timing}] {def.evt.name}: {def.evt.text}" + "\n\n" +
                $"공격력: {def.card.attack}    체력: {data.curHP} / {def.card.hp}"
            );
        }

        private static string ResolveClass(UnitType unitType) => unitType switch
        {
            UnitType.Leader => "군주",
            UnitType.Bishop => "비숍",
            UnitType.Knight => "나이트",
            UnitType.Rook => "룩",
            UnitType.Pawn => "폰",
            _ => "???",
        };
    }
}