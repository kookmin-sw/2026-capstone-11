[AttributeUsage(AttributeTargets.Class)]
public class CardEffectAttribute(string id) : Attribute
{
    public readonly string Id = id;
}
