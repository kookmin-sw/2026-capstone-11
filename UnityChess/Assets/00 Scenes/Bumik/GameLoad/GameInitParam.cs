using UnityEngine;

public class GameInitParam : MonoBehaviour
{
    public static GameInitParam Instance;

    [Header ("Game Session Data")]
    public string Player1Name;
    public string Player1Deck;


    [Header ("Network Data")]
    public string IpAddr;
    public int PortNum;

    public void Start()
    {
        if (Instance != null)
        {
            Destroy(gameObject);
            return;
        } 
        else Instance = this;
    }

    public void Clear()
    {
        Player1Name = "";
        Player1Deck = "";

        IpAddr = "";
        PortNum = 0;
    }
}
