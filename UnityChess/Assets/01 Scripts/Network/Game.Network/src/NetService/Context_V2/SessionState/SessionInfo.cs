using System;
using System.Diagnostics.Tracing;
using System.IO.Compression;

namespace Game.Network.Service
{
    public interface ISessionInfoReader
    {
        public SessionInfo.State state {get;}
        public SessionId id {get;}
        public SessionPlayerId playerId {get;}
    }

    public interface ISessionInfoWriter : ISessionInfoReader
    {
        public void Bind(SessionId id);
        public void Enter(SessionPlayerId id);
        public void Exit();
        public void ExitUnsafe();
    }


    public class SessionInfo : ISessionInfoWriter
    {
        public enum State
        {
            None,
            Entering,
            Entered,
            Exit,
            ExitUnsafe,
        }

        private State _state = State.None; 
        private Session? _session = null;
        private SessionId _sessionId = SessionId.Default;
        private SessionPlayerId _playerId = SessionPlayerId.Default;

        public State state => _state;
        public SessionId id => _sessionId;
        public SessionPlayerId playerId => _playerId;

        public void Bind(SessionId id)
        {
            _state = State.Entering;
            _sessionId = id;
        }

        public void Enter(SessionPlayerId playerId)
        {
            if (_state != State.Entering || _sessionId == SessionId.Default) throw new InvalidOperationException();
            _state = State.Entered;
            _playerId = playerId;
        }

        public void Exit()
        {
            _state = State.Exit;
            _sessionId = SessionId.Default;
            _playerId = SessionPlayerId.Default;
        }

        public void ExitUnsafe()
        {
            _state = State.ExitUnsafe;
        }

    }
}