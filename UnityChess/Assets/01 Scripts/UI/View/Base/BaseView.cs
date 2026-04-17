using events;
using UnityEngine;
using core.data;

namespace ui.view
{
    public abstract class BaseView : MonoBehaviour, IView
    {
        [SerializeField] protected BaseViewData viewData;
        [SerializeField] protected IEventBus eventBus;
        [SerializeField] protected CardDefinition definition;

        // ViewData 접근 (getter)
        public ViewID Id => viewData.Id;
        public ViewType Type => viewData.Id.Type;

        public virtual void Init(BaseViewData data, IEventBus eventBus)
        {
            viewData = data;
            this.eventBus = eventBus;

            if (eventBus == null)
            {
                Debug.LogError("EventBus is not assigned in BaseView.");
            }
            else
            {
                Debug.Log($"BaseView initialized with ID: {Id.UUID}, Type: {Type}");
            }
        }

        public virtual void SetDefinition(CardDefinition def)
        {
            // 뷰에서 카드 정의를 받아서 초기화하는 용도
            definition = def;
        }

        public abstract void Subscribe();

        public abstract void UnSubscribe();
    }
}
