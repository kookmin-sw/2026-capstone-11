using events;

namespace ui.view
{
    public interface IView
    {
        public void Init(BaseViewData data, IEventBus eventBus);

        public void Subscribe();
        public void UnSubscribe();
    }
}
