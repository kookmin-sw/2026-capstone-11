using System;
using UnityEngine;
using System.Collections.Generic;

namespace events.ui
{
    public class ChessUIEventBus : MonoBehaviour, IEventBus
    {
        // 싱글톤 인스턴스
        private static ChessUIEventBus _instance;
        public static ChessUIEventBus Instance;

        // 싱글톤 초기화 구현
        void Awake()
        {
            if (!_instance)
            {
                _instance = this;
                Instance = _instance;
            }
            else
            {
                Destroy(gameObject);
            }
        }

        // 이벤트 구독자 목록
        private Dictionary<Type, List<Action<BaseEvent>>> subscribers = new Dictionary<Type, List<Action<BaseEvent>>>();

        public void Publish<T>(T eventData) where T : BaseEvent
        {
            Type eventType = typeof(T);

            if (subscribers.ContainsKey(eventType))
            {
                foreach (var callback in subscribers[eventType])
                {
                    callback(eventData);
                }
            }
        }

        public void Subscribe<T>(Action<T> callback) where T : BaseEvent
        {
            Type eventType = typeof(T);

            if (!subscribers.ContainsKey(eventType))
            {
                subscribers[eventType] = new List<Action<BaseEvent>>();
            }

            subscribers[eventType].Add((e) => callback((T)e));
        }

        public void Unsubscribe<T>(Action<T> callback) where T : BaseEvent
        {
            Type eventType = typeof(T);

            if (subscribers.ContainsKey(eventType))
            {
                subscribers[eventType].Remove((e) => callback((T)e));
            }
        }
    }
    
}
