using System;
using Animations;
using entity.targetable;
using events;
using events.client;
using ui.tooltip;
using ui.view.effect;
using UnityEngine;
using UnityEngine.UI;

namespace ui.view.card
{
    /// <summary>
    /// 카드 뷰에 필요한 데이터 클래스
    /// </summary>
    public class CardViewData : BaseViewData
    {
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
    public class CardView : BaseView, IHoverable, IHightlighter
    {
        public CardViewData data;
        public Image image;
        public CardAnimator cardAnimator;
        public CardOutliner cardOutliner;

        public override void Init(BaseViewData baseData, IEventBus eventBus)
        {
            base.Init(baseData, eventBus);
            data = (CardViewData)baseData;
        }

        public TooltipData GetTooltipData()
        {
            return TooltipBuilder.CardTooltip(definition);
        }

        public void SetCardSprite(Sprite sprite)
        {
            image.sprite = sprite;
            cardOutliner.Init(sprite);
        }

        public override void SetHighlight(OutlineType type)
        {
            cardOutliner.SetHighlight(type);
            cardAnimator.SetSelected(type == OutlineType.Selected);
        }

        public void OnSelected()
        {
            Debug.Log("Card selected: " + data.cardId);
        }

        public override void Subscribe()
        {
            eventBus.Subscribe<IClientEvents.CardSelectedEvent>(OnSelected);
        }

        private void OnSelected(IClientEvents.CardSelectedEvent evt)
        {
            throw new NotImplementedException();
        }

        public override void UnSubscribe()
        {
            eventBus.Unsubscribe<IClientEvents.CardSelectedEvent>(OnSelected);
        }
    }
}