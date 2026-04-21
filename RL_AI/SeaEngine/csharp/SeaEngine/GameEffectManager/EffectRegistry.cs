using System.Reflection;
using SeaEngine.GameEffectManager.Effects;
using SeaEngine.GameEffectManager.Effects.Generic;

namespace SeaEngine.GameEffectManager;

public class EffectRegistry
{
    private static EffectRegistry? _instance;
    private Dictionary<string, IEffect> _registry = new Dictionary<string, IEffect>();
    private static readonly bool _verboseLog = Environment.GetEnvironmentVariable("SEAENGINE_VERBOSE_EFFECT_REGISTRY_LOG") == "1";

    private static void Init()
    {
        if (_verboseLog) Console.WriteLine("Initializing EffectRegistry...");
        _instance = new EffectRegistry();
    }

    private EffectRegistry()
    {
        var types = Assembly.GetExecutingAssembly().GetTypes()
            .Where(t => t.GetCustomAttribute<EffectAttribute>() != null);

        foreach (var type in types)
        {
            if (_verboseLog) Console.WriteLine("Registering effect " + type.Name);
            var attr = type.GetCustomAttribute<EffectAttribute>();
            if(attr == null) continue;
            var effect = (IEffect?)Activator.CreateInstance(type);
            if (effect == null) continue;
            _registry.Add(effect.Id, effect);
        }
    }

    public static IEffect Get(string id)
    {
        if(_instance == null) Init();
        if (_instance != null && _instance._registry.TryGetValue(id, out var effect))
        {
            return effect;
        }
        //return new ER_L();
        throw new KeyNotFoundException($"Effect with id {id} not found");
    }
}
