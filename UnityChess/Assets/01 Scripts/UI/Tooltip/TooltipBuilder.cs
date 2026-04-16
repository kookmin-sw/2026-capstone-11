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
                header: $"[유닛/클래스 : {def.card.unitType}]\n",
                description: $"[{def.evt.timing}] {def.evt.name}: {def.evt.text}" + "\n" +
                $"공격력: {def.card.attack} \t 체력: {def.card.hp}\n"
            );
        }

        public static TooltipData SpellCardTooltip(CardDefinition def)
        {
            return new TooltipData(
                title: def.card.name,
                header: $"[스펠/클래스 : {def.card.unitType}]\n",
                description: $"{def.effect.name}: {def.effect.text}" + "\n"
            );
        }

        public static TooltipData UnitOnboardTooltip(CardDefinition def, UnitViewData data)
        {
            return new TooltipData(
                title: def.card.name,
                header: $"[유닛/클래스 : {def.card.unitType}]\n",
                description: $"[{def.evt.timing}] {def.evt.name}: {def.evt.text}" + "\n" +
                $"공격력: {def.card.attack} \t 체력: {data.curHP} / {def.card.hp}\n"
            );
        }
    }
}