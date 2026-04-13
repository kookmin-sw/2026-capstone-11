using events;
using UnityEngine;

namespace ui.view
{
    public abstract class BaseView : MonoBehaviour, IView
    {
        protected BaseViewData viewData;
        protected IEventBus eventBus;

        // ViewData 접근 (getter)
        public ViewID Id => viewData.Id;
        public ViewType Type => viewData.Id.Type;

        public virtual void Init(BaseViewData data, IEventBus eventBus)
        {
            viewData = data;
            this.eventBus = eventBus;
        }

        public abstract void Subscribe();

        public abstract void UnSubscribe();
    }
}
