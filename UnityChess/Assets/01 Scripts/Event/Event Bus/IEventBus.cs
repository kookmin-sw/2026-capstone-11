namespace events
{
    public interface IEventBus
    {
        public void Publish<T>(T eventData) where T : BaseEvent;
        public void Subscribe<T>(System.Action<T> callback) where T : BaseEvent;
        public void Unsubscribe<T>(System.Action<T> callback) where T : BaseEvent;
    }
}
