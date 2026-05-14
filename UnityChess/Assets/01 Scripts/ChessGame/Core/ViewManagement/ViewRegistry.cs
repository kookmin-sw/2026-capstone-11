using System;
using System.Collections.Generic;
using ui.view;
using UnityEngine;

namespace core.UI
{
    /// <summary>
    /// 뷰들을 관리하는 레지스트리 클래스
    /// </summary>
    public class ViewRegistry: MonoBehaviour
    {
        private Dictionary<ViewID, IView> views = new Dictionary<ViewID, IView>();

        /// <summary>
        /// 뷰 등록
        /// </summary>
        /// <param name="view, id"></param>
        public void Register(IView view, ViewID id)
        {
            if (views.ContainsKey(id))
            {
                throw new Exception($"{id} 뷰가 이미 존재합니다.");
            }

            views.Add(id, view);
        }

        /// <summary>
        /// 뷰 등록 해제
        /// </summary>
        /// <param name="id"></param>
        public void Unregister(ViewID id)
        {
            if (!views.ContainsKey(id))
            {
                throw new Exception($"{id} 뷰가 존재하지 않습니다.");
            }

            views.Remove(id);
        }

        /// <summary>
        /// 뷰가 존재하는지 여부를 반환
        /// </summary>
        /// <param name="id"></param>
        /// <returns></returns>
        public bool Contains(ViewID id)
        {
            return views.ContainsKey(id);
        }

        /// <summary>
        /// id에 해당하는 뷰를 반환
        /// </summary>
        /// <param name="id"></param>
        /// <returns></returns>
        public IView Get(ViewID id)
        {
            views.TryGetValue(id, out IView view);
            return view;
        }
        
        /// <summary>
        /// 등록된 모든 뷰 ID를 반환
        /// </summary>
        /// <returns></returns>
        public List<ViewID> GetAllIds()
        {
            return new List<ViewID>(views.Keys);
        }
    }
}
