namespace SeaEngine.Common;

public class Uid
{
    private static readonly Dictionary<string, int> _cur = new Dictionary<string, int>();
    
    private readonly string _id;
    public Uid(string prefix)
    {
        _cur.TryAdd(prefix, 0);
        _id = $"{prefix}{_cur[prefix]:X3}";
        _cur[prefix] += 1;
    }

    private Uid(string prefix, int id)
    {
        _id = $"{prefix}{id:X2}";
    }

    private Uid(string id, bool ignore)
    {
        _id = id;
    }

    public static readonly Uid None = new Uid("",0);

    public override string ToString()
    {
        return _id;
    }

    public bool Equals(Uid other)
    {
        return _id == other._id;
    }

    public override int GetHashCode()
    {
        return _id.GetHashCode();
    }

    public static Uid Parse(string id)
    {
        return new Uid(id, true);
    }
}