using System;
using UnityEngine;

namespace ui.view.board
{
    /// <summary>
    /// 보드 셀의 Transform을 관리하는 보드 뷰 클래스
    /// </summary>
    public class BoardView : MonoBehaviour
    {
        [SerializeField]
        public Transform[,] cells;
        public GameObject boardParent;

        public const int SIZE = 6;

        public void Init()
        {
            cells = new Transform[SIZE, SIZE];

            GameObject[] cellTmp = GameObject.FindGameObjectsWithTag("Cell");
        }
    }
}

