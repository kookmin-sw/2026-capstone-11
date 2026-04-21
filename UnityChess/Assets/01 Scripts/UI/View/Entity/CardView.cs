using System;
using entity.targetable;
using events;
using events.client;
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
            // if (data.visualType == VisualType.UnitCard)
            // {
            //     return TooltipBuilder.UnitCardTooltip(definition);
            // }
            // else // VisualType.SpellCard
            // {
            //     return TooltipBuilder.SpellCardTooltip(definition);
            // }

            // 유닛과 효과 설명을 함께 표시하는 카드 툴팁 (후보)
            return TooltipBuilder.CadTooltip(definition);
        }

        public void OnSelected()
        {
            Debug.Log("Card selected: " + data.cardId);
        }

        public override void Subscribe()
        {
            eventBus.Subscribe<IClientEvents.CardSelectedEvent>(OnSelected);
        }

        private void OnSelected(IClientEvents.CardSelectedEvent @event)
        {
            throw new NotImplementedException();
        }

        public override void UnSubscribe()
        {
            eventBus.Unsubscribe<IClientEvents.CardSelectedEvent>(OnSelected);
        }
    }
}