
namespace Game.Network 
{
    public class ConnId : IEquatable<ConnId>
    {
        private readonly Guid _id;

        private ConnId(Guid id) { _id = id; }
        public static ConnId Get() 
            => new ConnId(Guid.NewGuid());

        public static ConnId Default()
            => new ConnId (Guid.Empty);


        public bool Equals(ConnId other) => _id == other._id;
        public override bool Equals(object? obj) => obj is ConnId other && Equals(other);

        public override int GetHashCode()
        { 
            return _id.GetHashCode();;
        }

        public override string ToString()
        {
            return _id.ToString();
        }

        public static bool operator ==(ConnId id_1, ConnId id_2) => id_1.Equals(id_2);

        public static bool operator !=(ConnId id_1, ConnId id_2) => !id_1.Equals(id_2);
        
    }
}