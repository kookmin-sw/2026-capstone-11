namespace SeaEngine.Common;

public record Uid
{
    //TODO : prefix에 따른 Uid의 Factory를 생성하도록 재작성하기.
    
    private readonly string _id;

    public Uid(string prefix, int id)
    {
        _id = $"{prefix}{id:X3}";
    }

    private Uid(string id)
    {
        _id = id;
    }

    public override string ToString()
    {
        return _id;
    }

    public static Uid Parse(string id)
    {
        return new Uid(id);
    }
    
    public static readonly Uid None = new Uid("",0);
}