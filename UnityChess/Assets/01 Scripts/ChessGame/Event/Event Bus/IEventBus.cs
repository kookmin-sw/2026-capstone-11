namespace events
{
    public interface IEventBus
    {
        public void Publish<T>(T eventData) where T : IBaseEvent;
        public void Subscribe<T>(System.Action<T> callback) where T : IBaseEvent;
        public void Unsubscribe<T>(System.Action<T> callback) where T : IBaseEvent;
    }
}
