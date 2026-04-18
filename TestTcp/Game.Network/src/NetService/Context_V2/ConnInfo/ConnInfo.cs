

using System.IO.Compression;
using System.Security.Permissions;
using Game.Network.Protocol;

namespace Game.Network.Service
{
    public interface IConnInfoReader
    {
        public NetworkType networkType {get;}
        public ConnectionType connectionType {get;}
        public string PlatformName {get;}
        public string AccountId {get;}
        public string AppVersion {get;}
    }

    public interface IConnInfoWriter : IConnInfoReader
    {
        public void SetNetworkType(NetworkType type);
        public ConnInfo instance {get;}
    }

    public class ConnInfo : IConnInfoWriter
    {
        public static ConnInfoCodec Codec = new();

        private NetworkType _netType;
        private ConnectionType _connType;
        private string _platformName;
        private string _accountId;
        private string _appVersion;

        public NetworkType networkType => _netType;
        public ConnectionType connectionType => _connType;
        public string PlatformName => _platformName;
        public string AccountId => _accountId;
        public string AppVersion => _appVersion;

        public void SetNetworkType(NetworkType type) { _netType = type; }
        public ConnInfo instance {get => this;}

        public ConnInfo()
        {
            _netType = NetworkType.Disconnect;
            _connType = ConnectionType.Client;
            _platformName = String.Empty;
            _accountId = String.Empty;
            _appVersion = String.Empty;
        }

        public ConnInfo(string PlatformName, string AccountId, string AppVersion, bool IsHost = false)
        {
            _netType = NetworkType.Disconnect;
            _connType = (IsHost) ? ConnectionType.Host : ConnectionType.Client;
            _platformName = PlatformName ?? String.Empty;
            _accountId = AccountId ?? String.Empty;
            _appVersion = AppVersion ?? String.Empty;
        }
        public ConnInfo(NetworkType networkType, ConnectionType connectionType, string PlatformName, string AccountId, string AppVersion)
        {
            _netType = networkType;
            _connType = connectionType;
            _platformName = PlatformName ?? String.Empty;
            _accountId = AccountId ?? String.Empty;
            _appVersion = AppVersion ?? String.Empty;
        }
    };




}