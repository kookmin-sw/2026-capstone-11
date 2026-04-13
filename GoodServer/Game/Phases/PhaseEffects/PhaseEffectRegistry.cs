using System.Reflection;
using System.Runtime.CompilerServices;
using GoodServer.Game.Effects;

namespace GoodServer.Game.Phases.PhaseEffects;

public class PhaseEffectRegistry
{
    private static PhaseEffectRegistry? _instance;
    private readonly Dictionary<Phase, IEffect> _registry = new Dictionary<Phase, IEffect>();

    [ModuleInitializer]
    public static void Init()
    {
        _instance = new PhaseEffectRegistry();
    }
    private PhaseEffectRegistry()
    {
        var types = Assembly.GetExecutingAssembly().GetTypes()
            .Where(t => t.GetCustomAttribute<PhaseEffectAttribute>() != null);

        foreach (var type in types)
        {
            PhaseEffectAttribute? attr = type.GetCustomAttribute<PhaseEffectAttribute>();
            if (attr == null) continue;
            IEffect? effect = (IEffect?)Activator.CreateInstance(type);
            if (effect == null) continue;
            _registry[attr.Phase] = effect;
            Console.WriteLine("Register Phase " + attr.Phase + " : " + effect.Description);
        }
    }

    public static IEffect? Get(Phase phase)
    {
        return _instance._registry.GetValueOrDefault(phase);
    }
}