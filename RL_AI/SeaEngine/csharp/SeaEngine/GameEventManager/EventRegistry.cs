using System.Reflection;
using SeaEngine.GameEffectManager;

namespace SeaEngine.GameEventManager;

public class EventRegistry
{
    private static EventRegistry? _instance;
    private Dictionary<string, Dictionary<string, IEvent>> _registry = new Dictionary<string, Dictionary<string, IEvent>>();

    private static void Init()
    {
        _instance = new EventRegistry();
    }

    private EventRegistry()
    {
        var types = Assembly.GetExecutingAssembly().GetTypes()
            .Where(t => t.GetCustomAttribute<EventAttribute>() != null);

        foreach (var type in types)
        {
            var attr = type.GetCustomAttribute<EventAttribute>();
            if(attr == null) continue;
            var eventInstance = (IEvent?)Activator.CreateInstance(type);
            if (eventInstance == null) continue;
            if(!_registry.ContainsKey(eventInstance.Timing)) _registry.Add(eventInstance.Timing, new Dictionary<string, IEvent>());
            _registry[eventInstance.Timing].Add(eventInstance.Id, eventInstance);
        }
    }

    public static IEvent? GetEvent(string timing,string id)
    {
        if (_instance == null) Init();
        if (_instance == null) return null;
        if (!_instance._registry.TryGetValue(timing, out var timedEvents)) return null;
        return timedEvents.GetValueOrDefault(id);
    }
}
