using entity.targetable;
using events;
using ui.tooltip;
using UnityEngine;

namespace ui.view.card
{
    public enum VisualType
    {
        UnitCard,  // 소환 전 유닛 카드
        SpellCard, // 소환 후 스펠 카드
    }

    /// <summary>
    /// 카드 뷰에 필요한 데이터 클래스
    /// </summary>
    public class CardViewData : BaseViewData
    {
        public VisualType visualType;

        public CardViewData(ViewID id,
                            ViewType type,
                            string cardId,
                            VisualType visualType) : base(id, type)
        {
            this.cardId = cardId;
            this.visualType = visualType;
        }
    }

    /// <summary>
    /// 카드 뷰의 공통 클래스
    /// </summary>
    public class CardView : BaseView, IHoverable
    {
        public CardViewData data;

        public override void Init(BaseViewData baseData, IEventBus eventBus)
        {
            base.Init(baseData, eventBus);
            data = (CardViewData)baseData;
        }

        public TooltipData GetTooltipData()
        {
            // 시점에 따라 유닛 카드 또는 스펠 카드 툴팁을 반환
            if (data.visualType == VisualType.UnitCard)
            {
                return TooltipBuilder.UnitCardTooltip(definition);
            }
            else // VisualType.SpellCard
            {
                return TooltipBuilder.SpellCardTooltip(definition);
            }
        }

        public override void Subscribe()
        {
            
        }

        public override void UnSubscribe()
        {
            
        }
    }
}