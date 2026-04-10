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

    public static readonly Uid None = new Uid("",0);

    public override string ToString()
    {
        return _id;
    }

    public bool Equals(Uid other)
    {
        return _id == other._id;
    }

    public override bool Equals(object? obj)
    {
        return obj is Uid other && Equals(other);
    }

    public override int GetHashCode()
    {
        return _id.GetHashCode();
    }

    public static bool operator ==(Uid? left, Uid? right)
    {
        if (ReferenceEquals(left, right)) return true;
        if (left is null || right is null) return false;
        return left.Equals(right);
    }

    public static bool operator !=(Uid? left, Uid? right)
    {
        return !(left == right);
    }
}
