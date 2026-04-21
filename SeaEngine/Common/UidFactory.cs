namespace SeaEngine.Common;

public class UidFactory
{
    public string Prefix { get; }
    private int _cur = 0;

    public UidFactory(string prefix)
    {
        this.Prefix = prefix;
    }

    public Uid Next()
    {
        return new Uid(Prefix, ++_cur);
    }
}