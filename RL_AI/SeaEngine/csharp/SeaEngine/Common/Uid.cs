namespace SeaEngine.Common;

public record Uid
{
    
    //TODO : prefix에 따른 Uid의 Factory를 생성하도록 재작성하기.
    
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
        _id = $"{prefix}{id:X3}";
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

    public static Uid Parse(string id)
    {
        return new Uid(id, true);
    }
}