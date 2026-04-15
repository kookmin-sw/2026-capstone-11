using System.Reflection;
using System.Runtime.CompilerServices;
using GoodServer.Game.Effects;

namespace GoodServer.Game.Cards;

public class CardEffectRegistry
{
    private static CardEffectRegistry? _instance;
    private Dictionary<string, IEffect> _registry = new();

    [ModuleInitializer]
    public static void Init()
    {
        _instance = new CardEffectRegistry();
    }

    private CardEffectRegistry()
    {
        var types = Assembly.GetExecutingAssembly().GetTypes()
            .Where(t => t.GetCustomAttribute<CardEffectAttribute>() != null);

        foreach (var type in types)
        {
            var attr = type.GetCustomAttribute<CardEffectAttribute>();
            if(attr == null) continue;
            var effect = (IEffect?)Activator.CreateInstance(type);
            if(effect == null) continue;
            _registry[attr.Id] = effect;
            Console.WriteLine("Register Card : " + attr.Id + "->" + effect.Description);
        }
    }

    public static IEffect Get(string id)
    {
        return _instance._registry.GetValueOrDefault(id);
    }
}