using UnityEditor.PackageManager;
using UnityEngine;

public class GameInitializer : MonoBehaviour
{
    public static GameInitializer Instance;
    public GameInitializeData Data;

    public void Start()
    {
        if (Instance != null)
        {
            Destroy(gameObject);
            return;
        } 
        else Instance = this;

        Data = new();
    }
}
