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
        public string cardId;
        public CardViewData(ViewID id,
                            ViewType type,
                            string cardId) : base(id, type)
        {
            this.cardId = cardId;
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
            return TooltipBuilder.UnitCardTooltip(definition);
        }
    }

    /// <summary>
    /// 소환 후 스펠 카드 뷰
    /// </summary>
    public class SpellCardView : CardView
    {
        public override TooltipData GetTooltipData()
        {
            return TooltipBuilder.SpellCardTooltip(definition);
        }
    }
}