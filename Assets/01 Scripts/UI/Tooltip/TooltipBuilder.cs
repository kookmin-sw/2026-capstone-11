using entity.targetable;
using ui.view.card;
using ui.view.unit;

namespace ui.tooltip
{
    /// <summary>
    /// 툴팁 데이터를 생성하는 빌더 클래스
    /// </summary> 
    public static class TooltipBuilder
    {
        public static TooltipData UnitCardTooltip(CardViewData data)
        {
            return new TooltipData(
                title: data.name,
                header: $"[유닛/클래스 : {data.className}]\n",
                description: data.traitsDesc + "\n" +
                $"공격력: {data.attack} \t 체력: {data.maxHP}\n"+
                $"소환 / 이동 코스트: {data.moveCost}"
            );
        }

        public static TooltipData SpellCardTooltip(CardViewData data)
        {
            return new TooltipData(
                title: data.name,
                header: $"[스펠/클래스 : {data.className}]\n",
                description: data.spellDesc + "\n" +
                $"사용 코스트: {data.spellCost}"
            );
        }

        public static TooltipData UnitOnboardTooltip(UnitViewData data)
        {
            return new TooltipData(
                title: data.name,
                header: $"[유닛/클래스 : {data.className}]\n",
                description: data.traitsDesc + "\n" +
                $"공격력: {data.attack} \t 체력: {data.currentHP} / {data.maxHP}\n"+
                $"이동 코스트: {data.moveCost}"
            );
        }
    }
}