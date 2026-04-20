using System;
using UnityEngine;
using UnityEngine.Tilemaps;
using System.Collections.Generic;

namespace ui.view.board
{
    /// <summary>
    /// 보드 셀의 Transform을 관리하는 보드 뷰 클래스
    /// </summary>
    public class BoardView : MonoBehaviour
    {
        public GameObject boardParent;

        public const int SIZE = 6;
        public const int ORIGIN_X = -2;
        public const int ORIGIN_Y = -2;

        public Tilemap tilemap;
        public TileBase highlightTile;
        private List<Vector3Int> current = new();

        // 보드 셀 좌표를 받아서 해당 셀에 하이라이트 표시
        public void Show(HashSet<Vector2Int> cells)
        {
            Clear();

            foreach (var c in cells)
            {
                var cell = BoardToCell(c);
                Debug.Log($"[BoardView.Show] board={c} -> tileCell={cell}");
                tilemap.SetTile(cell, highlightTile);
                current.Add(cell);
            }
        }

        // 보드의 모든 하이라이트 제거
        public void Clear()
        {
            foreach (var c in current)
            {
                tilemap.SetTile(c, null);
            }
            current.Clear();
        }

        // 보드 좌표로부터 타일맵 셀 좌표 계산
        public static Vector3Int BoardToCell(Vector2Int boardPos, bool isP1 = true)
        {
            int bx = boardPos.y + ORIGIN_X; // x, y 스왑
            int by = boardPos.x + ORIGIN_Y; // x, y 스왑
            
            if (!isP1)
            {
                bx = (SIZE - 1) - bx;
                by = (SIZE - 1) - by;
            }

            Debug.Log($"BoardToCell: Board({boardPos.x}, {boardPos.y}) -> Cell({bx}, {by})");
            return new Vector3Int(bx-1, by-1, 2);
        }

        // 타일맵 셀 좌표로부터 보드 좌표 계산
        public static Vector2Int CellToBoard(Vector3Int cellPos, bool isP1 = true)
        {
            int bx = cellPos.x - ORIGIN_X;
            int by = cellPos.y - ORIGIN_Y;

            if (!isP1)
            {
                bx = (SIZE - 1) - bx;
                by = (SIZE - 1) - by;
            }

            Debug.Log($"CellToBoard: Cell({cellPos.x}, {cellPos.y}) -> Board({by}, {bx})");
            return new Vector2Int(by, bx);
        }
    }
}

