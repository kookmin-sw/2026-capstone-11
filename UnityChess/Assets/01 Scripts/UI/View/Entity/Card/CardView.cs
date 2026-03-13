using entity.targetable;
using events;
using ui.tooltip;
using UnityEngine;

namespace ui.view.card
{
    /// <summary>
    /// 카드 뷰에 필요한 데이터 클래스
    /// </summary>
    public class CardViewData : BaseViewData
    {
        // 공통
        public string name;
        public string className;

        // 유닛 정의
        public int attack;
        public int maxHP;
        public string traitsDesc; // 특성 설명 텍스트

        // 스펠 정의 (설명 텍스트)
        public string spellDesc;

        // 비용
        public int moveCost;
        public int spellCost;

        public CardViewData(ViewID id,
                            ViewType type,
                            string name,
                            string className,
                            int attack,
                            int maxHP,
                            string traitsDesc,
                            string spellDesc,
                            int moveCost,
                            int spellCost) : base(id, type)
        {
            this.name = name;
            this.className = className;
            this.attack = attack;
            this.maxHP = maxHP;
            this.traitsDesc = traitsDesc;
            this.spellDesc = spellDesc;
            this.moveCost = moveCost;
            this.spellCost = spellCost;
        }
    }

    /// <summary>
    /// 카드 뷰의 공통 클래스
    /// </summary>
    public abstract class CardView : BaseView, IHoverable
    {
        public CardViewData data;

        public override void Init(BaseViewData baseData, IEventBus eventBus)
        {
            base.Init(baseData, eventBus);
            data = (CardViewData)baseData;
        }

        public abstract TooltipData GetTooltipData();

        public override void Subscribe()
        {
            
        }

        public override void UnSubscribe()
        {
            
        }
    }

    /// <summary>
    /// 소환 전 유닛 카드 뷰
    /// </summary>
    public class UnitCardView : CardView
    {
        public override TooltipData GetTooltipData()
        {
            return TooltipBuilder.UnitCardTooltip(data);
        }
    }

    /// <summary>
    /// 소환 후 스펠 카드 뷰
    /// </summary>
    public class SpellCardView : CardView
    {
        public override TooltipData GetTooltipData()
        {
            return TooltipBuilder.SpellCardTooltip(data);
        }
    }
}